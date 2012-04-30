import os, os.path, sys, traceback
import shutil
import cmd
import jsonpickle
import tempfile
import zipfile

from openmdao.gui.util import *
from openmdao.main.publisher import Publisher

def modifies_files(target):
    ''' decorator for methods that change something in the file collection
        publishes the updated file collection information
    '''
    def wrapper(self, *args, **kwargs):
        result = target(self, *args, **kwargs)
        if self.publish_updates:
            self.publish_files()
        return result
    return wrapper
	
class FileManager(object):
    ''' Object that keeps track of a collection of files (i.e. a directory)
        and optionally publishes an update when the collection is modified
    '''

    def __init__(self, name, path=None, publish_updates=False):
        self.name = name
        
        self.orig_dir = os.getcwd()
        if path:
            self.root_dir = path
        else:
            self.root_dir = tempfile.mkdtemp(self.name)
        if os.path.exists(self.root_dir):
            shutil.rmtree(self.root_dir)
        os.mkdir(self.root_dir)
        os.chdir(self.root_dir)        
        print 'root_dir=',self.root_dir
        
        self.publish_updates = publish_updates
        self.publisher = None
        
    def publish_files(self):
        ''' publish the current file collection
        '''
        if not self.publisher:
            try:
                self.publisher = Publisher.get_instance()
            except Exception,err:
                print 'Error getting publisher:',err
                self.publisher = None
                
        if self.publisher:
            self.publisher.publish(self.name, self.get_files())

    def getcwd(self):
        ''' return the current working directory
        '''
        return os.getcwd()

    def cleanup(self):
        ''' Cleanup this server's directory. 
        '''
        os.chdir(self.orig_dir)
        if os.path.exists(self.root_dir):
            try:
                shutil.rmtree(self.root_dir)
            except Exception, err:
                self._error(err,sys.exc_info())

    def get_files(self):
        ''' get a nested dictionary of files in the working directory
        '''
        cwd = os.getcwd()
        return filedict(cwd,root=cwd)

    def get_file(self,filename):
        ''' get contents of file in working directory
            returns None if file was not found
        '''
        filepath = os.getcwd()+'/'+str(filename)
        if os.path.exists(filepath):
            contents=open(filepath, 'rb').read()
            return contents
        else:
            return None
    
    @modifies_files
    def ensure_dir(self,dirname):
        ''' create directory in working directory
            (does nothing if directory already exists)
        '''
        dirpath = os.getcwd()+'/'+str(dirname)
        if not os.path.isdir(dirpath):
            os.makedirs(dirpath)

    @modifies_files
    def write_file(self,filename,contents):
        ''' write contents to file in working directory
        '''
        try:
            filepath = os.getcwd()+'/'+str(filename)
            fout = open(filepath,'wb')
            fout.write(contents)
            fout.close()
            return True
        except Exception, err:
            return err

    @modifies_files
    def add_file(self,filename,contents):
        ''' add file to working directory
            if it's a zip file, unzip it
        '''
        self.write_file(filename, contents)
        if zipfile.is_zipfile(filename):
            userdir = os.getcwd()
            zfile = zipfile.ZipFile( filename, "r" )
            zfile.printdir()
            for fname in zfile.namelist():
                if fname.endswith('/'):
                    dirname = userdir+'/'+fname
                    if not os.path.exists(dirname):
                        os.makedirs(dirname)
            for fname in zfile.namelist():
                if not fname.endswith('/'):
                    data = zfile.read(fname)
                    fname = userdir+'/'+fname
                    fname = fname.replace('\\','/')
                    fout = open(fname, "wb")
                    fout.write(data)
                    fout.close()
            zfile.close()
            os.remove(filename)

    @modifies_files
    def delete_file(self,filename):
        ''' delete file in working directory
            returns False if file was not found, otherwise returns True
        '''
        filepath = os.getcwd()+'/'+str(filename)
        if os.path.exists(filepath):
            if os.path.isdir(filepath):
                os.rmdir(filepath)
            else:
                os.remove(filepath)
            return True
        else:
            return False
