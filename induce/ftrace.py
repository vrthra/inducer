#!/usr/bin/env python3

from typing import Dict, Tuple, Any, Optional, List, BinaryIO

import sys
import pickle
import inspect
import json
import os
import re
import fnmatch
from . import tstr
import bdb

# pylint: disable=multiple-statements,fixme, unidiomatic-typecheck
# pylint: line-too-long

# TODO: Figure out how globals fits into this.
# Globals are like self in that it may also be considered an input.
# However, if there is a shadowing local variable, we should ignore
# the global.

def decorate(stem: str, key: str, sep: str = '.') -> str:
    """Prepend a prefix to key"""
    return '%s%s%s' % (stem, sep, key)

class Tracer(bdb.Bdb):

    class_cache: Dict[Any, str] = {}

    """
    Extremely dumb Tracer for tracing the execution of functions
    """
    def __init__(self, in_data: str, tfile: BinaryIO) -> None:
        self.method = self.tracer()
        self.in_data = in_data
        self.trace_file = tfile
        self.trace_i = 0
        self.listeners = {'call', 'return', 'line'}
        cfg = os.getenv('trace.config')
        self._my_files = []
        self._skip_classes = []
        if cfg:
            self.conf = json.load(open(cfg))
            self._my_files = self.conf['my_files']
            self._skip_classes = self.conf['skip_classes']

    def __enter__(self) -> None:
        """ set hook """
        event = {'event': 'start', '$input': self.in_data}
        self.out(event)
        self.oldtrace = sys.gettrace()
        sys.settrace(self.method)
        return self

    def __exit__(self, typ: str, value: str, backtrace: Any) -> None:
        """ unhook """
        sys.settrace(self.oldtrace) #type: ignore
        self.out({'event': 'stop'})

    def out(self, val: Dict[str, Any]) -> None:
        pickle.dump(val, self.trace_file)

    def f_code(self, c: Any) -> Dict[str, Any]:
        return {'co_argcount': c.co_argcount,
                'co_code':c.co_code,
                'co_cellvars':c.co_cellvars,
                'co_consts':[(type(c).__name__,str(c)) for c in c.co_consts],
                'co_filename':c.co_filename,
                'co_firstlineno':c.co_firstlineno,
                'co_flags':c.co_flags,
                'co_lnotab':c.co_lnotab,
                'co_freevars':c.co_freevars,
                'co_kwonlyargcount':c.co_kwonlyargcount,
                'co_name':c.co_name,
                'co_names':c.co_names,
                'co_nlocals':c.co_nlocals,
                'co_varnames':c.co_varnames
                }

    def f_var(self, v: Dict[str, Any]) -> Dict[str, Any]:
        def process(v: Any) -> Any:
            tv = type(v)
            if tv in [str, int, float, complex, str, bytes, bytearray]:
                return v
            elif tv in [set, frozenset, list, tuple, range]:
                return tv([process(i) for i in v])
            elif tv in [dict]: # or hasattr(v, '__dict__')
                return {i:process(v[i]) for i in v}
            else:
                return tstr.get_t(v)
        return {i:process(v[i]) for i in v}

    def frame(self, f: Any) -> Dict[str, Any]:
        return {'f_code':self.f_code(f.f_code),
                # 'f_globals':self.f_var(f.f_globals),
                'f_locals':self.f_var(f.f_locals),
                'f_lasti':f.f_lasti,
                'f_back':self.frame(f.f_back) if f.f_back else None,
                'f_lineno':f.f_lineno,
                'f_context': Tracer.get_context(f)}

    def skip(self, frame):
        f, l, n, ls, i = self.loc(frame)
        c = Tracer.get_context(frame)
        if not self._my_files: return False
        for pattern in self._skip_classes:
            if re.search(pattern, c):
                return True
        for pattern in self._my_files:
            if fnmatch.fnmatch(f, pattern):
                return False
        return True


    def loc(self, c: Any) -> Tuple[str, str, int]:
        (f, line, name, lines, index) = inspect.getframeinfo(c)
        """ Returns location information of the caller """
        return (f, line, name, lines, index)

    def tracer(self) -> Any:
        """ Generates the trace function that gets hooked in.  """

        def traceit(frame: Any, event: str, arg: Optional[str]) -> Any:
            """ The actual trace function """
            vself = frame.f_locals.get('self')
            if self.skip(frame):
                return
            # dont process if the frame is tracer
            # this happens at the end of trace -- Tracer.__exit__
            if type(vself) == Tracer: return
            if event not in self.listeners: return

            frame_env = {'frame': self.frame(frame), 'loc': self.loc(frame),
                    'i': self.trace_i, 'event': event, 'arg': arg}
            self.out(frame_env)
            self.trace_i += 1
            return traceit
        return traceit

    @classmethod
    def set_cache(cls, code: Any, clazz: str) -> str:
        """ Set the global class cache """
        cls.class_cache[code] = clazz
        return clazz

    @classmethod
    def get_class(cls, frame: Any) -> Optional[str]:
        """ Set the class name"""
        code = frame.f_code
        name = code.co_name
        if cls.class_cache.get(code): return cls.class_cache[code]
        args, _, _, local_dict = inspect.getargvalues(frame)
        class_name = ''

        if name == '__new__':  # also for all class methods
            class_name = local_dict[args[0]].__name__
            return class_name
        try:
            class_name = local_dict['self'].__class__.__name__
            if class_name: return class_name
        except (KeyError, AttributeError):
            pass

        # investigate __qualname__ for class objects.
        for objname, obj in frame.f_globals.items():
            try:
                if obj.__dict__[name].__code__ is code:
                    return cls.set_cache(code, objname)
            except (KeyError, AttributeError):
                pass
            try:
                if obj.__slot__[name].__code__ is code:
                    return cls.set_cache(code, objname)
            except (KeyError, AttributeError):
                pass
        return "@"

    @classmethod
    def get_qualified_name(cls, frame: Any) -> str:
        """ Set the qualified method name"""
        code = frame.f_code
        name = code.co_name  # type: str
        clazz = cls.get_class(frame)
        if clazz: return decorate(clazz, name)
        return name

    @classmethod
    def get_context(cls, frame: Any) -> List[Tuple[str, int]]:
        """
        Get the context of current call. Switch to
        inspect.getouterframes(frame) if stack is needed
        """
        return Tracer.get_qualified_name(frame)

    # run vaiable to check whether its arrived at a breakpoint or not
    run = 0

    @classmethod
    def user_call(self, frame, args):
        name = frame.f_code.co_name or "<unknown>"
        print("call", name, args)
        self.set_continue() # continue

    @classmethod
    def user_line(self, frame):
        if self.run:
            self.run = 0
            self.set_trace() # start tracing
        else:
            # arrived at breakpoint
            name = frame.f_code.co_name or "<unknown>"
            filename = self.canonic(frame.f_code.co_filename)
            print("break at", filename, frame.f_lineno, "in", name)
        print("continue...")
        self.set_continue() # continue to next breakpoint

    @classmethod
    def user_return(self, frame, value):
        name = frame.f_code.co_name or "<unknown>"
        print("return from", name, value)
        print("continue...")
        self.set_continue() # continue

    @classmethod
    def user_exception(self, frame, exception):
        name = frame.f_code.co_name or "<unknown>"
        print("exception in", name, exception)
        print("continue...")
        self.set_continue() # continue
