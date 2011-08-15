import tempfile
from subprocess import call
import subprocess 
import os
import linecache
import redis
from cgi import parse_qs, escape

log = ["Starting validation process"]
GIT_DIR = "/home/git/git_repo.git"
log_dir = "/home/git/public/log/%s.html"
log_html_dir = "/log/%s.html"
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
# Main procedure where all the action happens
#
def main():
   global tmp_repo
   tmp_repo = tempfile.mkdtemp(dir="/home/git/tmp")
   project_root = tmp_repo + "/book.asc"

   #
   # Clone file into working repo
   # 

   status_log.rpush(log_key, "Starting conversion")
   try: 
      rc = call(["git", "clone", "--no-hardlinks", GIT_DIR, tmp_repo])
   except Exception, e:
      write_log("<b>Unable to unpack file %s<b>" % tmp_repo)
      raise ValidationError("Error unpacking file")
   

   #
   # Test if book.asc exists 
   # 
   if not os.path.exists(project_root):
      write_log("<b>Unable to find book.asc</b>")
      raise ValidationError("Error deleting")

   
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
      lines = stdout_value.split("\n")[1:]
      write_log("%s lines" % str(len(lines)))
      write_log("<ul>")
      for line in lines: 
          write_log("<li>" + line + "</li>")
      write_log("</ul>")
   except Exception, e:
      write_log("... Could not convert book to asciidoc")
      raise ValidationError("Error converting asciidoc to docbook")

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
   except Exception, e:
      write_log("... Error running xmllint")
      raise ValidationError("Error validating")


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
      fn = tmp_repo.split("/")[-1]
      rc = call (['mv', "%s/book.epub" % tmp_repo, "/home/git/public/epub/%s.epub" % fn])
      write_log("<a href='%s'>Download EPUB</a>" % ("/epub/%s.epub" % fn)) 
      status_log.rpush(log_key, "Epub File is %s" % ("/epub/%s.epub" % fn))
   except Exception, e:
      write_log("... Unable to delete files")
      raise ValidationError("Unable to delete files")


   #
   # Clone file into working repo
   # 
   status_log.rpush(log_key,"Cleaning up files")
   write_log("Cleaning up files")
   try: 
      pass
      rc = call(["rm", "-rf", tmp_repo])
   except Exception, e:
      write_log("... Unable to delete files")
      raise ValidationError("Error deleteing")
   
   status_log.rpush(log_key,"Conversion complete")


   # Save log to a file
   fn = tmp_repo.split("/")[-1]
   status_log.rpush(log_key, "Log file : %s" % (log_html_dir % fn)) 
   write_log("<a href='%s'>Log file</a>" % (log_html_dir % fn)) 
   f = open(log_dir % fn, "w")
   f.write("<p>".join(log))
   f.close()  
#
# Main mod_wsgi interface
#
def application(environ, start_response):

   global log
   global log_key

   # Get the Redis log key from the command line
   qs = parse_qs(environ['QUERY_STRING'])
   log_key = qs.get('log_key', ["log1000"])[0]
   log_key = escape(log_key)

   log = ["Starting validation process"]
   log = ["Log key is %s" % log_key]
   status_log.expire(log_key,3600)

   try:
      main()
   except:
      write_log("Some error occurred!")

   status = '200 OK'
   output = "<p>".join(log)


   response_headers = [('Content-type', 'text/html'),
                        ('Content-Length', str(len(output)))]
   start_response(status, response_headers)

   return [output]
