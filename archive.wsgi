import tempfile
from subprocess import call
import subprocess 
import os

GIT_DIR = "/home/git/git_repo.git"
DEST = "/home/git/tmp/archive.zip"

#
# Main procedure where all the action happens
#
def main():
   #
   # Clone file into working repo
   # 
   cmd = [
      "cd %s;" % GIT_DIR,
      "git",
      "archive",
      "-o",
      DEST,
      "HEAD"
   ]

   try:
      proc = subprocess.Popen(" ".join(cmd),
         shell=True,
         stderr=subprocess.STDOUT,
         stdout = subprocess.PIPE)
      stdout_value, stderr_value = proc.communicate()
   except Exception as e:
      pass


#
# Main mod_wsgi interface
#
def application(environ, start_response):

   main()
   status = '200 OK'
   response_headers = [
      ('Content-type', 'application/octet-stream'),
      ('Content-disposition', 'attachment; filename=archive.zip')
   ]

   start_response(status, response_headers)

   filelike = file("/home/git/tmp/archive.zip", "rb")
   block_size = 4096 

   if 'wsgi.file_wrapper' in environ:
      return environ['wsgi.file_wrapper'](filelike, block_size)
   else:
      return iter(lambda: filelike.read(block_size), '')
