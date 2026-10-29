"""Keep model inference in a process that can be stopped independently."""
import multiprocessing
import traceback


def _serve(connection, factory):
    synth = factory()
    try:
        while True:
            args = connection.recv()
            try:
                synth.synthesize(*args)
                connection.send(None)
            except Exception as exc:
                traceback.print_exc()
                connection.send(str(exc))
    except EOFError:
        pass
    finally:
        connection.close()


class SpeechProcess:
    def __init__(self, factory):
        self.factory = factory
        self.process = None
        self.connection = None

    def close(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
            self.process.close()
            self.process = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def synthesize(self, *args, check):
        check()
        if self.process is None:
            ctx = multiprocessing.get_context('spawn')
            self.connection, child = ctx.Pipe()
            self.process = ctx.Process(target=_serve, args=(child, self.factory), daemon=True)
            self.process.start()
            child.close()
        try:
            self.connection.send(args)
            while not self.connection.poll(.1):
                check()
                if not self.process.is_alive():
                    raise RuntimeError('Speech engine exited unexpectedly. Retry the job.')
            check()
            error = self.connection.recv()
            if error is not None:
                raise RuntimeError(error)
        except BaseException:
            self.close()
            raise
