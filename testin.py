
import os, sys, commands, re, threading, Queue, subprocess, signal, thread

class AsynchronousFileReader(threading.Thread):
    '''
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.
    '''

    def __init__(self, fd, queue):
        assert isinstance(queue, Queue.Queue)
        assert callable(fd.readline)
        threading.Thread.__init__(self)
        self._fd = fd
        self._queue = queue

    def run(self):
        '''The body of the tread: read lines and put them on the queue.'''
        for line in iter(self._fd.readline, ''):
            self._queue.put(line)

    def eof(self):
        '''Check whether there is no more content to expect.'''
        return not self.is_alive() and self._queue.empty()

class devices(object):
    def __init__(self):
        pass
    def enumdevices(self):
        l = []
        output = subprocess.check_output(['adb','devices'],shell=True)#commands.getoutput('adb devices')
        m = re.findall(r'.*\n+(.+)\s+device', output)
        l[:] = [d for d in m]
        return l
    
class targets(object):
    def __init__(self, config):
        self.config = config

    def analyse(self, t):
        l = []
        l.append(t)
        output = subprocess.check_output(['aapt', 'dump', 'badging', t], shell=False)
        r = re.findall(r'package: name=\'(.+?)\'.*', output)
        l.append(r[0])
        r = re.findall(r'launchable-activity: name=\'(.+?)\'.*', output)
        l.append(r[0])
        return l
    def load(self):
        r = []
        l = []
        with open(self.config, 'r') as f:
            l[:] = [t.strip() for t in f.readlines()]
        for t in l:
            r.append(self.analyse(t))
        self.targetlist = r
        return r
    
    def unload(self):
        pass
    
class logcat(object):
    def __init__(self, d):
        subprocess.check_output(['adb', '-s', d, 'logcat', '-c'], shell=False)
        self.funclist = []
        self.device = d
        self.process = subprocess.Popen(['adb', '-s', self.device, 'logcat'], stdout=subprocess.PIPE)
        self.stdout_queue = Queue.Queue()
        self.stdout_reader = AsynchronousFileReader(self.process.stdout, self.stdout_queue)
        self.stdout_reader.start()
    
    def addfilter(self, callback):
       
        self.funclist.append(callback)
        
    def capture(self):
        while not self.stdout_reader.eof():
            while not self.stdout_queue.empty():
                line = self.stdout_queue.get()
                for f in self.funclist:
                    f[0](f[1], f[2], f[3], line)
                
    def exit(self):
        self.process.kill()
        
class testin(object):
    def __init__(self, config):
        self.devices = devices()
        self.targets = targets(config)
        self.logcatlist = []
        
        self.d = self.devices.enumdevices()
        self.t = self.targets.load()        
    def thread_logcat(self, l):
        l.capture()
        
    def install(self):
        for d in self.d:
            for t in self.t:
                subprocess.check_output(['adb', '-s', d, 'uninstall', t[1]], shell=False)
                subprocess.check_output(['adb', '-s', d, 'install', t[0]], shell=False)   
    def uninstall(self):
        for d in self.d:
            for t in self.t:
                subprocess.check_output(['adb', '-s', d, 'uninstall', t[1]], shell=False)               
    
    def testit(self):
        for d in self.d:
            l = logcat(d)
            self.logcatlist.append(l)
            for t in self.t:
                l.addfilter([filter, d, t[0], str.format(r'.+Displayed\s{0}.+:\s\+(.+?)ms', t[1])])
                thread.start_new_thread(self.thread_logcat, (l,))
                
                subprocess.check_output(['adb', '-s', d, 'uninstall', t[1]], shell=False)
                subprocess.check_output(['adb', '-s', d, 'install', t[0]], shell=False)
                subprocess.check_output(['adb', '-s', d, 'shell', 'am start -n', str.format('{0}/{1}', t[1], t[2])], shell=False)
           

def filter(device, apk, regex, text):
    r = re.match(regex, text)
    if r:
        print str.format('[+]\tin {0} {1} Display used time ***[{2}ms]*** and logcat[{3}]', device, apk, r.group(1), r.group(0))
        
def handler(signum, frame):
    if signum == 2:
        for d in g_testin.d:
            for t in g_testin.t:
                subprocess.check_output(['adb', '-s', d, 'uninstall', t[1]], shell=False)

global g_testin

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print '--auto config       auto install auto start auto uninstall\n'
        print '--install           just install\n'
        print '--uninstall         just uninstall\n'
        exit()

    signal.signal(signal.SIGINT, handler)
    g_testin = testin(sys.argv[2])
    
    if sys.argv[1] == '--auto':
        g_testin.testit()
    if sys.argv[1] == '--install':
        g_testin.install()
    if sys.argv[1] == '--uninstall':
        g_testin.uninstall()