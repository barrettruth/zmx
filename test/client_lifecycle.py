#!/usr/bin/env python3
"""Run isolated PTY scenarios: python3 test/client_lifecycle.py /path/to/zmx [nvim]."""
import errno
import contextlib
import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time

ZMX = str(Path(sys.argv[1]).resolve())
NVIM = sys.argv[2] if len(sys.argv) > 2 else None
LEGACY = os.environ.get("ZMX_LEGACY_BINARY")


class Client:
    def __init__(self, env, name, command, binary=ZMX):
        self.master, self.slave = pty.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        self.attrs = termios.tcgetattr(self.slave)
        self.flags = fcntl.fcntl(self.slave, fcntl.F_GETFL)
        self.pending = bytearray()
        self.output = bytearray()
        self.proc = subprocess.Popen([binary, "attach", name, *command], env=env,
                                     stdin=self.slave, stdout=self.slave, stderr=self.slave,
                                     start_new_session=True)

    def wait(self, marker):
        deadline = time.monotonic() + 15
        while marker not in self.pending:
            remaining = deadline - time.monotonic()
            assert remaining > 0, (marker, self.output[-500:], self.proc.poll())
            assert select.select([self.master], [], [], remaining)[0], (marker, self.output[-500:])
            try:
                chunk = os.read(self.master, 65536)
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise
                chunk = b""
            assert chunk, (marker, self.output[-500:])
            self.pending.extend(chunk)
            self.output.extend(chunk)
        end = self.pending.index(marker) + len(marker)
        result = bytes(self.pending[:end])
        del self.pending[:end]
        return result

    def send(self, data):
        os.write(self.master, data)

    def finish(self, success=True):
        self.wait(b"\x1bc")
        code = self.proc.wait(timeout=5)
        assert (code == 0) == success, code
        assert self.output.count(b"\x1bc") == 1, self.output
        assert termios.tcgetattr(self.slave) == self.attrs
        assert fcntl.fcntl(self.slave, fcntl.F_GETFL) & os.O_NONBLOCK == self.flags & os.O_NONBLOCK

    def fd_count(self):
        proc_dir = Path(f"/proc/{self.proc.pid}/fd")
        if proc_dir.is_dir():
            return len(list(proc_dir.iterdir()))
        data = subprocess.check_output(["lsof", "-a", "-p", str(self.proc.pid), "-F", "f"])
        return sum(line[1:].isdigit() for line in data.splitlines() if line.startswith(b"f"))


with tempfile.TemporaryDirectory(prefix="zmx-life-", dir="/tmp") as directory:
    base = Path(directory)
    env = dict(os.environ)
    for key in ("ZMX_SESSION", "ZMX_SESSION_PREFIX", "TMUX", "TMUX_PANE"):
        env.pop(key, None)
    env.update(ZMX_DIR=str(base / "sockets"), SHELL="/bin/sh", TERM="xterm-256color")
    clients = []
    sessions = set()

    def cli(*args, session=None):
        child_env = dict(env)
        if session:
            child_env["ZMX_SESSION"] = session
        return subprocess.check_output([ZMX, *args], env=child_env,
                                       stderr=subprocess.PIPE, timeout=15)

    def attach(name, *command):
        sessions.add(name)
        client = Client(env, name, command)
        clients.append(client)
        return client

    program = base / "session.py"
    program.write_text('''import os, signal, sys, tty
tty.setraw(0)
name = sys.argv[1].encode()
def resized(*_):
    size = os.get_terminal_size(0)
    os.write(1, ("SIZE:%d:%d\\r\\n" % (size.columns, size.lines)).encode())
signal.signal(signal.SIGWINCH, resized)
os.write(1, b"READY:" + name + b"\\r\\n")
line = bytearray()
while True:
    c = os.read(0, 1)
    if not c: break
    if c != b"\\n":
        line.extend(c)
        continue
    if line == b"exit": break
    os.write(1, b"EVENT:" + name + b":" + line + b"\\r\\n")
    line.clear()
''')

    def create(name):
        client = attach(name, sys.executable, str(program), name)
        client.wait(b"READY:" + name.encode())
        return client

    def detach(client, name):
        cli("detach", session=name)
        client.finish()

    def switch(client, source, target):
        cli("attach", target, session=source)
        client.wait(b"READY:" + target.encode())
        marker = ("switch-%d" % len(client.output)).encode()
        client.send(marker + b"\n")
        client.wait(b"EVENT:" + target.encode() + b":" + marker)
        assert b"\x1bc" not in client.output

    try:
        first = create("first")
        second = attach("first")
        second.wait(b"READY:first")
        second.send(b"leader\n")
        second.wait(b"EVENT:first:leader")
        cli("detach", session="first")
        first.finish()
        second.finish()

        target = create("target")
        detach(target, "target")
        client = attach("first")
        client.wait(b"READY:first")
        switch(client, "first", "target")
        count = client.fd_count()
        current = "target"
        for _ in range(40):
            other = "first" if current == "target" else "target"
            switch(client, current, other)
            current = other
        assert client.fd_count() == count
        client.send(b"after-switches\n")
        client.wait(b"EVENT:target:after-switches")
        fcntl.ioctl(client.slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
        os.kill(client.proc.pid, signal.SIGWINCH)
        client.wait(b"SIZE:100:30")
        detach(client, current)
        print("detach-all, repeated switching, descriptors, resize: passed", flush=True)

        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            for switched in (False, True):
                client = attach("first")
                client.wait(b"READY:first")
                current = "first"
                if switched:
                    switch(client, "first", "target")
                    current = "target"
                os.kill(client.proc.pid, sig)
                client.finish()
                assert b"READY:" + current.encode() in cli("history", current)
        print("TERM, HUP, INT before and after switching: passed", flush=True)

        client = attach("first")
        client.wait(b"READY:first")
        client.send(b"\x1c")
        client.finish()
        client = create("natural")
        client.send(b"exit\n")
        client.finish()
        client = create("killed")
        cli("kill", "killed")
        client.finish()
        print("detach key, process exit, session kill: passed", flush=True)

        client = attach("first")
        client.wait(b"READY:first")
        sessions.add("created")
        cli("attach", "created", session="first")
        client.send(b"printf 'CREATED_READY\\n'\r")
        client.wait(b"CREATED_READY\r\n")
        cli("detach", session="created")
        client.finish()
        client = attach("created")
        client.wait(b"CREATED_READY")
        client.send(b"exit\r")
        client.finish()

        client = attach("first")
        client.wait(b"READY:first")
        invalid = base / "sockets" / "invalid"
        invalid.write_text("not a socket")
        cli("attach", "invalid", session="first")
        client.finish(success=False)
        invalid.unlink()
        print("new target and failed target: passed", flush=True)

        if sys.platform == "darwin":
            client = attach("first")
            client.wait(b"READY:first")

            def children():
                rows = subprocess.check_output(["ps", "-axo", "pid=,ppid="]).splitlines()
                return {int(row.split()[0]) for row in rows
                        if int(row.split()[1]) == client.proc.pid}

            before = children()
            sessions.add("daemon-error")
            cli("attach", "daemon-error", session="first")
            client.send(b"printf 'CHILD_READY\\n'\r")
            client.wait(b"CHILD_READY\r\n")
            daemon_pid, = children() - before
            with contextlib.closing(select.kqueue()) as queue:
                # Darwin NOTE_EXITSTATUS returns the process's wait status.
                queue.control([select.kevent(daemon_pid, filter=select.KQ_FILTER_PROC,
                               flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                               fflags=select.KQ_NOTE_EXIT | 0x04000000)], 0)
                detach(client, "daemon-error")
                # A switch without a leader causes daemonLoop to return an error.
                cli("attach", "first", session="daemon-error")
                event, = queue.control(None, 1, 5)
                assert os.waitstatus_to_exitcode(event.data) == 1
            print("forked daemon error cleanup: passed", flush=True)

        if LEGACY:
            sessions.add("legacy")
            client = Client(env, "legacy", [sys.executable, str(program), "legacy"], LEGACY)
            clients.append(client)
            client.wait(b"READY:legacy")
            detach(client, "legacy")
            client = attach("legacy")
            client.wait(b"READY:legacy")
            client.send(b"compatible\n")
            client.wait(b"EVENT:legacy:compatible")
            os.kill(client.proc.pid, signal.SIGTERM)
            client.finish()
            print("attachment to a legacy daemon: passed", flush=True)

        if NVIM:
            document = base / "document.txt"
            document.write_text("EDITOR_READY\n")
            editor = base / "editor.py"
            editor.write_text('import os, subprocess, sys, tty\ntty.setraw(0)\nsubprocess.run([sys.argv[1], "--clean", "-n", sys.argv[2]])\nos.write(1, b"EDITOR_EXITED")\nos.read(0, 1)\n')
            client = attach("editor", sys.executable, str(editor), NVIM, str(document))
            client.wait(b"EDITOR_READY")
            detach(client, "editor")
            client = attach("editor")
            client.wait(b"EDITOR_READY")
            os.kill(client.proc.pid, signal.SIGTERM)
            client.finish()
            client = attach("editor")
            client.wait(b"EDITOR_READY")
            client.send(b":qa!\r")
            client.wait(b"EDITOR_EXITED")
            client.send(b"q")
            client.finish()
            print("Neovim detach, termination, reattach, exit: passed", flush=True)
    finally:
        for name in sessions:
            subprocess.run([ZMX, "kill", name, "--force"], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        for client in clients:
            if client.proc.poll() is None:
                client.proc.terminate()
                client.proc.wait(timeout=5)
            os.close(client.master)
            os.close(client.slave)
        assert cli("list", "--short").strip() == b""
