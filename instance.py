"""同一个配置文件仅允许一个进程运行；使用系统文件锁，无额外依赖。"""
from contextlib import contextmanager
from pathlib import Path
import os


class AlreadyRunningError(RuntimeError):
    pass


@contextmanager
def single_instance(config_path):
    lock_path = Path(str(Path(config_path).resolve()) + ".lock")
    with lock_path.open("a+b") as lock_file:
        if lock_file.tell() == 0:
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise AlreadyRunningError("同一配置的反戳程序已运行，请勿重复启动") from exc
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise AlreadyRunningError("同一配置的反戳程序已运行，请勿重复启动") from exc
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
