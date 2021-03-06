#!/usr/bin/env python
import os
import shutil
import subprocess
import sys
import time


def subprocess_on_vm(vm, command):
    return subprocess.Popen(['vagrant', 'ssh', vm, '--', command])


if __name__ == '__main__':
    if '--fast' not in sys.argv:
        # Cleanup CFFI-related files
        shutil.rmtree(
            os.path.abspath(os.path.join(os.path.dirname(__file__), '../../gssapi/bindings/autogenerated.cdef')),
            ignore_errors=True
        )
        shutil.rmtree('client.keytab', ignore_errors=True)
        shutil.rmtree('server.keytab', ignore_errors=True)

        subprocess.check_call(('vagrant', 'up'))

        for vm in ('server', 'client'):
            subprocess_on_vm(vm, 'sudo python2 -m pip install -r /python-gssapi/test_requirements.txt').wait()
            subprocess_on_vm(vm, 'sudo pypy -m pip install -r /python-gssapi/test_requirements.txt').wait()
            subprocess_on_vm(vm, 'sudo python3 -m pip install -r /python-gssapi/test_requirements.txt').wait()
            subprocess_on_vm(vm, 'cd /python-gssapi && sudo python2 setup.py install').wait()
            subprocess_on_vm(vm, 'cd /python-gssapi && sudo pypy setup.py install').wait()
            subprocess_on_vm(vm, 'cd /python-gssapi && sudo python3 setup.py install').wait()

    server_procs = [
        subprocess_on_vm('server', 'cd /python-gssapi && sudo python2 tests/integration/server.py')
    ]
    time.sleep(1)
    server_procs.append(subprocess_on_vm('server', 'cd /python-gssapi && sudo pypy tests/integration/server.py'))
    time.sleep(1)
    server_procs.append(subprocess_on_vm('server', 'cd /python-gssapi && sudo python3 tests/integration/server.py'))

    print("Wait for server procs to start...")
    time.sleep(5)

    client_procs = (
        subprocess_on_vm('client', ' && '.join((
            'echo "userpassword" | kinit -f testuser',
            'cd /python-gssapi',
            'python2 /usr/local/bin/nosetests-2.7 --with-xunit --xunit-file py2tests.xml tests.integration.test_client:ClientIntegrationTest'
        ))),
        subprocess_on_vm('client', ' && '.join((
            'echo "userpassword" | kinit -f testuser',
            'cd /python-gssapi',
            'pypy /usr/local/bin/nosetests-2.7 --with-xunit --xunit-file pypy2tests.xml tests.integration.test_client:ClientIntegrationTest'
        ))),
        subprocess_on_vm('client', ' && '.join((
            'echo "userpassword" | kinit -f testuser',
            'cd /python-gssapi',
            'python3 /usr/local/bin/nosetests-3.4 --with-xunit --xunit-file py3tests.xml tests.integration.test_client:ClientIntegrationTest'
        ))),
    )

    print("wait for client_procs")
    for index, client_proc in enumerate(client_procs):
        client_proc.wait()
        if client_proc.returncode == 0:
            print("wait for server proc {0}".format(index))
            server_procs[index].wait()
        else:
            print("client_proc {0} exited with status {1}, terminating server".format(
                index, client_proc.returncode
            ))
            server_procs[index].terminate()

    # Clean up any old server processes
    subprocess_on_vm('server', 'sudo pkill -f tests/integration/server.py')
