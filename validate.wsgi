import tempfile
from subprocess import call
import subprocess 
import os
import linecache
import redis
from cgi import parse_qs, escape

log = ["Starting validation process"]
GIT_DIR = "/home/git/git_repo.git"
log_dir = "/home/git/gollum/lib/gollum/frontend/public/log/%s.html"
epub_dir = "/home/git/gollum/lib/gollum/frontend/public/epub/%s.epub"
pdf_dir = "/home/git/gollum/lib/gollum/frontend/public/epub/%s.pdf"
log_html_dir = "/log/%s.html"
log_url = ""
epub_url = ""
process_status = ""
tmp_repo = ""

status_log = redis.Redis(host="localhost", port=6379, db=0)
log_key = "key:1000"

#
# Define a generic exception
#
class ValidationError(Exception):
   def __init__(self,value):
      self.value = value
   def __str__(self):
      return repr(self.value)

#
# Used to log output
#
def write_log(msg):
   log.append(msg)

#
# Processes the raw error log from xmllint
#
def process_results(err, src):
   lines = err.split("\n")
   idx = 0
   for line in lines:
      fields = line.split("\n")[0].split(":")
      if len(fields) == 5:
         idx += 1
         write_log("***************************************")
         write_log("Error %s" % str(idx))
         write_log("<textarea rows=5 cols=80>" + repr(line) + "</textarea>")
         write_log("The error occurred around the following lines:")
         file_ln = int(fields[1])
         out = []
         for l in range(file_ln-5, file_ln+5):
            out.append(linecache.getline(src,l))   
         write_log("<textarea rows=5 cols=80>" + "".join(out) + "</textarea>")
   if idx == 0:
      write_log("No errors found.")  

#
# Creates an include file from the index file
#
def write_index(doc_path, root):
   fn_in = "%s/%s.asciidoc" % (doc_path, root)
   fn_out = "%s/book.asciidoc" % doc_path
   try:
      f_out = open(fn_out,'w')
      f_in = open(fn_in,'r')
      lines = f_in.readlines()
      for l in lines:
         rec = ' '.join(l.split()).split(" ") #Nice little hack to clean up whitespace and EOL
         if (rec[0] == "*"): 
            out = "include::%s.asciidoc[]\n\n" % rec[1]
            f_out.write(out)
      f_out.close()
      f_in.close()
   except Exception as e:
      write_log("<b>Unable to create index file %s<b>" % f_out)
      raise ValidationError(str(e))

#
# Main procedure where all the action happens
#
def main():
   global tmp_repo
   tmp_repo = tempfile.mkdtemp(dir="/home/git/tmp")
   project_root = tmp_repo + "/book.asciidoc"

   #
   # Clone file into working repo
   # 
   status_log.rpush(log_key, "Starting conversion")
   try: 
      rc = call(["git", "clone", "--no-hardlinks", GIT_DIR, tmp_repo])
      rc = call(["rm", log_dir % "book"])
      rc = call(["rm", epub_dir % "book"])
      rc = call(["rm", pdf_dir % "book"])
   except Exception as e:
      write_log("<b>Unable to unpack file %s<b>" % tmp_repo)
      raise ValidationError(str(e))

   #
   # Create the "book.asc" file
   # 
   write_index(tmp_repo, root)   

   #
   # Converting to asciidoc 
   # 
   status_log.rpush(log_key,"Converting AsciiDoc to DocBook")
   write_log("Converting %s from AsciiDoc into DocBook" % project_root)
   try: 
      proc = subprocess.Popen("asciidoc -b docbook %s" % project_root,
          shell=True, 
          stderr=subprocess.STDOUT,
          stdout = subprocess.PIPE)
      stdout_value, stderr_value = proc.communicate()
      # Now print the results
      write_log("<hr><h1>Asciidoc Error Log</h1>")
      lines = stdout_value.split("\n")
      write_log("<ul>")
      for line in lines: 
          write_log("<li>" + line + "</li>")
      write_log("</ul>")
   except Exception as e:
      write_log("... Could not convert book to asciidoc")
      raise ValidationError(str(e))

   #
   # Running XMLLINT, which send output to STDERR.  So, this part is a bit 
   # different in that it must read from STDERR with the communicate() method 
   # 

   status_log.rpush(log_key,"Validating DocBook")
   write_log("Running xmllint to validate docbook")
   try: 
      proc = subprocess.Popen("xmllint --valid --noout %s/book.xml 2>&1" % tmp_repo,
          shell=True, 
          stderr=subprocess.STDOUT,
          stdout = subprocess.PIPE)
      stdout_value, stderr_value = proc.communicate()
      write_log("<hr><h1>DocBook Error Log</h1>")
      process_results(stdout_value, tmp_repo+"/book.xml")
      if len(stdout_value.split("\n")) > 1:
         raise ValidationError("DocBook file contains errors")
   except Exception as e:
      write_log("... Error running xmllint")
      raise ValidationError(str(e))


   #
   # Generate EPUB from the DocBook XML
   #
   status_log.rpush(log_key,"Generating epub")
   write_log("Generating epub")
   dbtoepub = [
      "cd %s;" % tmp_repo,
      "/home/git/epub/docbook-xsl/epub/bin/dbtoepub",
      "-v",
      "-c", 
      "/home/git/epub/epub/core.css", 
      "-s", 
      "/home/git/epub/epub/core.xsl", 
      "-f", 
      "/home/git/epub/epub/fonts/LiberationSerif.otf", 
      "%s/book.xml" % tmp_repo
   ]
   try:
      proc = subprocess.Popen(" ".join(dbtoepub),
         shell=True,
         stderr=subprocess.STDOUT,
         stdout = subprocess.PIPE)
      stdout_value, stderr_value = proc.communicate()
      write_log("<hr><h1>EPUB Conversion</h1>")
      write_log(repr(stdout_value))
      # Now copy the epub over to the public EPUB directory where people can get the link
      fn = "book"
      rc = call (['mv', "%s/book.epub" % tmp_repo, epub_dir % fn])
      epub_url = "/epub/%s.epub" % fn
      status_log.set(log_key + "-epub",epub_url)
      write_log("<a href='%s'>Download EPUB</a>" % epub_url ) 
   except Exception as e:
      write_log("... Unable to delete files")
      raise ValidationError(str(e))

   #
   # Generate a PDF
   #
   status_log.rpush(log_key,"Generating PDF")
   write_log("Generating PDF")
   cmd = [
      "cd %s;" % tmp_repo,
      "a2x",
      "-fpdf",
      project_root
   ]
   try:
      proc = subprocess.Popen(" ".join(cmd),
         shell=True,
         stderr=subprocess.STDOUT,
         stdout = subprocess.PIPE)
      stdout_value, stderr_value = proc.communicate()
      write_log("<hr><h1>PDF Conversion</h1>")
      write_log(repr(stdout_value))
      # Now copy the epub over to the public EPUB directory where people can get the link
      fn = "book"
      rc = call (['mv', "%s/book.pdf" % tmp_repo, pdf_dir % fn])
      pdf_url = "/epub/%s.pdf" % fn
      status_log.set(log_key + "-pdf",pdf_url)
      write_log("<a href='%s'>Download PDF</a>" % pdf_url ) 
   except Exception as e:
      write_log("... Unable to create PDF")
      raise ValidationError(str(e))


   #
   # Remove old repo
   # 
   status_log.rpush(log_key,"Cleaning up files")
   write_log("Cleaning up files")
   try: 
      pass
      rc = call(["rm", "-rf", tmp_repo])
   except Exception as e:
      write_log("... Unable to delete files")
      raise ValidationError(str(e))
   
   status_log.rpush(log_key,"Conversion complete")
   status_log.set(log_key + "-status", "COMPLETE")

#
# Main mod_wsgi interface
#
def application(environ, start_response):

   global log
   global log_key
   global log_url
   global epub_url
   global process_status
   global root

   # Get the Redis log key from the command line
   qs = parse_qs(environ['QUERY_STRING'])
   log_key = qs.get('log_key', ["log1000"])[0]
   log_key = escape(log_key)

   # Get the root index file
   root = qs.get('root', ["book.asc"])[0]
   root = escape(root)

   log = ["Starting validation process"]
   log_url = ""
   epub_url = ""
   process_status = "RUNNING"

   status_log.expire(log_key,3600)
   status_log.expire(log_key + "-epub",3600)
   status_log.expire(log_key + "-key",3600)
   status_log.expire(log_key + "-status",3600)

   status_log.set(log_key + "-epub", epub_url) 
   status_log.set(log_key + "-log", log_url)
   status_log.set(log_key + "-status",  process_status)

   status_log.rpush(log_key,"Root document is %s" % root)
   write_log("Root document is %s" % root)

   try:
      main()
   except Exception as e:
      status_log.set(log_key + "-status", "ERROR") 
      write_log(str(e))

   # Save log to a file
#   fn = tmp_repo.split("/")[-1]
   fn = "log"
   status_log.set(log_key + "-log", "/log/%s.html" % fn)
   status_log.set(log_key + "-epub", "/epub/book.epub")
   write_log("<a href='%s'>Log file</a>" % "/log/%s.html" % fn ) 
   f = open(log_dir % fn, "w")
   f.write("<p>".join(log))
   f.close()  

   status = '200 OK'
   output = "<p>".join(log)


   response_headers = [('Content-type', 'text/html'),
                        ('Content-Length', str(len(output)))]
   start_response(status, response_headers)

   return [output]
