from selenium import webdriver, common
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.firefox.options import Options

import dbus
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

from datetime import datetime, timedelta
import sched, time, threading, signal
import functools

# 
username = ""
password = ""

table_res = {
    "14:00" : {
        "slot" : "8",
        "edificio" : "ED1",
        "aula" : " Edificio A  SPAZIO STUDIO 1 piano terra ala sx",
        "repr" : "SLOT 14.00 / 17.00",
        "id" : "SER12",
        "code": "SVINSER12",
    }, 
    "11:00" : {
        "slot" : "7",
        "edificio" : "ED1",
        "aula" : " Edificio A  SPAZIO STUDIO 1 piano terra ala sx",
        "repr" : "SLOT 11.00 / 14.00",
        "id" : "SER12",
        "code": "SVINSER12",
    }, 
    "17:00" : { "slot" : "9",
        "edificio" : "ED1",
        "aula" : " Edificio A  SPAZIO STUDIO 1 piano terra ala sx",
        "repr" : "SLOT 17.00 / 20.00",
        "id" : "SER12",
        "code": "SVINSER12",
    }, 
    "08:00" : {
        "slot" : "6",
        "edificio" : "ED1",
        "aula" : " Edificio A  SPAZIO STUDIO 1 piano terra ala sx",
        "repr" : "SLOT 08.00 / 11.00",
        "id" : "SER12",
        "code": "SVINSER12",
    }, 
    "20:00" : {
        "slot" : "10",
        "edificio" : "ED1",
        "aula" : " Edificio A  SPAZIO STUDIO 1 piano terra ala sx",
        "repr" : "SLOT 20.00 - 24.00 / 08.00",
        "id" : "SER12",
        "code": "SVINSER12",
    }, 
}

table_slot = {
    0 : "20:00",
    1 : "08:00", 6 : "08:00",
    2 : "11:00", 7 : "11:00",
    3 : "14:00", 8 : "14:00",
    4 : "17:00", 9 : "17:00",
    5 : "20:00", 10 : "20:00",
}

class sleeper:
    def __init__ (self, time):
        self.dbus_thread = threading.Thread(target=self.dbus_handler)
        self.cv = threading.Condition(lock=None)

        self.delta = 0
        self.time = time
        self.start = time()
        
    def handle_wakeup(self, s):
        with self.cv:
            if s == 0:
                self.delta = max(0, self.delta - (self.time() - self.start))
                self.start = self.time()
                self.cv.notify(n=1)

    def gdelta(self):
        t = self.delta
        self.delta = 0
        return t

    def __call__ (self, delta):
        self.delta = delta
        if not self.dbus_thread.is_alive():
            self.dbus_thread.start()
        with self.cv:
            while self.delta > 0:
                self.cv.wait(self.gdelta()); 

    def dbus_handler(self):
        DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus()
        bus.add_signal_receiver(               # define the signal to listen to
            self.handle_wakeup,                # callback function
            'PrepareForSleep',                 # signal name
            'org.freedesktop.login1.Manager',  # interface
            'org.freedesktop.login1'           # bus name
        )
        self.loop = GLib.MainLoop()
        self.loop.run()

    def shutdown(self):
        if self.dbus_thread.is_alive():
            self.loop.quit()
        
suspend_sleeper = sleeper(time.time)

class schedule:
    def __init__ (self, ts):
        self.vreturn = None
        self.tstart = ts

    def today(**tkw):
        return schedule(datetime.now().replace(**tkw))

    def tomorrow(**tkw):
        tmw = datetime.now() + timedelta(days=1)
        return schedule(tmw.replace(**tkw))

    def next(**tkw):
        rrep = datetime.now().replace(**tkw)
        return ((schedule.tomorrow if rrep < datetime.now()
            else schedule.today)(**tkw))   

    def runner(self):
        self.vreturn = self.func(*(self.args), **(self.kwargs))

    def __call__ (self, f):
        def job(*args, **kwargs):
            self.func = f
            self.args = args
            self.kwargs = kwargs

            s = sched.scheduler(time.time, suspend_sleeper)
            s.enterabs(time.mktime(self.tstart.timetuple()), 0,
                lambda x : x.runner(), argument=(self,), kwargs={})
            s.run()
            return self.vreturn

        return job

class Tasker:
    def __init__ (self):
        self.sched = sched.scheduler(time.time, suspend_sleeper)

    def today(**tkw):
        return datetime.now().replace(**tkw)

    def tomorrow(**tkw):
        tmw = datetime.now() + timedelta(days=1)
        return tmw.replace(**tkw)

    def next(**tkw):
        rrep = datetime.now().replace(**tkw)
        return ((Tasker.tomorrow if rrep < datetime.now()
            else Tasker.today)(**tkw))

    def append(self, f, tstart, args = ( ), kwargs = { }):
        self.sched.enterabs(time.mktime(tstart.timetuple()), 0,
            f, argument=args, kwargs=kwargs)
        return self

    def __call__ (self):
        self.sched.run()

class requires:
    def __init__ (self, reqs):
        if not all(map(len, reqs)):
            raise ValueError("username/password not defined")

    def __call__(self, f):
        return f
        
class cycle:
    ''' 
    Decoratore parametrizzato che invoca la funzione nucleo a intervalli 
    di regolari (assegnati con delta) fino allo scadere del tempo fissato (specifato 
    da **tkw) oppure alla raggiungimento dello scopo (segnalato dalla funzione
    con il valore di ritorno True)
    '''
    def __init__ (self, delta = None, sched = None):
        self.dt = delta
        self.sched = sched
        self.cond = True
        self.done = False

    def today(delta = None, **tkw):
        return cycle(delta=delta, sched=schedule.today(**tkw))

    def tomorrow(delta = None, **tkw):
        return cycle(delta=delta, sched=schedule.tomorrow(**tkw))

    def next(delta = None, **tkw):
        return cycle(delta=delta, sched=schedule.next(**tkw))

    def stopper(self):
        self.cond = False

    def __call__(self, f):
        self.stopper = self.sched(self.stopper)
        threading.Thread(target=self.stopper, daemon=True).start()
        def run(*args, **kwargs):
            if self.cond:
                self.done = f(*args, **kwargs)
            while self.cond and (not self.done):
                # prevent time overshooting
                net = (self.sched.tstart - datetime.now()).seconds
                time.sleep(min(net, self.dt))
                if self.dt > net:
                    break
                self.done = f(*args, **kwargs)
            return self.done

        return run

class multiple:
    '''
    higher-order decorator: applica a f passata in __call__, ciascun decorator
    finché la condizione di ritorno == true risulta vera su uno di questi o termina
    la lista dei decoratori
    '''
    def from_description(*args):
        return multiple([arg['decorator'](**arg['args']) for arg in args])

    def __init__ (self, cyls):
        self.cyls = cyls

    def __call__ (self, f):
        def run(*args, **kwargs):
            for cyl in self.cyls:
                if cyl(f)(*args, **kwargs):
                    break

        return run

class foreach:
    """
    applica alla funzione decorata un elemento per volta estranedolo dall'iterabile 
    args[self.idx] con ripetute chiamate
    """
    def __init__ (self, x):
        self.idx = x

    def __call__ (self, fn):
        def run(*args, **kwargs):
            for x in args[self.idx]:
                fn(*(args[:self.idx]), x, *(args[self.idx+1:]), **kwargs)

        return run

class task:
    def __init__(self, r, attempts=8, update = lambda t : t * 2):
        self.repair = r
        self.attempts = attempts
        self.update = update
        self.time = 1

    def __call__ (self, fn):
        def run(*args, **kwargs):
            while self.attempts > 0:
                try:
                    return fn(*args, **kwargs)
                except:
                    self.attempts -= 1
                    self.time = self.update(self.time)
                    time.sleep(self.time)
                    self.repair()
            # let it fail
            self.attempts = 8
        return run

def compose(*fs):
    def compose2(f, g):
        return lambda *args : f(*g(*args))
    return functools.reduce(compose2, fs)

# --- MAIN --- 

script = """
var callback = arguments[arguments.length - 1];

burl=base+"s4aapp2?f=" + arguments[0] + "&token=" + token + arguments[1];
axios.get(burl).then(response => {
    callback(response.data);
}).catch(err => {
    callback(-1);
});
"""

# TODO, handle fail connection with task
def login(driver):
    driver.get("https://gosafety.web.app/")

    WebDriverWait(driver, 30).until(
        expected_conditions.presence_of_element_located(
            (By.ID, 'ALL'),
        ))

    for vi, vv in ('v1', username), ('v2', password):
        el = driver.find_element(By.ID, vi)
        el.clear(); el.send_keys(vv)
    driver.find_element(By.CLASS_NAME, 'button_full').click()
    
    print("logged-in")

    WebDriverWait(driver, 30).until(
        expected_conditions.presence_of_element_located(
            (By.ID, 'MYPREN'),
        ))
    return driver

# invoke login on failure
@task(lambda : [driver.refresh(), login(driver)])
def query2(driver, action, payload, delay = 1):
    params = [action, ""]
    if payload:
        s = '&'.join(map(lambda x : "=".join(x), 
                zip(payload.keys(), payload.values())
            ))
        params[1] = '&' + s

    r = driver.execute_async_script(script, *params)
    if r == -1:
        raise RuntimeError
    return r

day_selector = datetime.today().replace(
    hour=20, minute=00, second=00) < datetime.now()

repr_compact = lambda x : x[:2] + x[3:]
repr_lengthy = lambda x : ':'.join((x[:2], x[2:]))

def _adjust_slot(repr_slot):
    return int(table_res[repr_slot]["slot"]) - 5 * (not day_selector)

def _missing_res(driver):
    stoday = datetime.today().strftime("%Y%m%d")

    res = query2(driver, "mypren", { })
    pres = list(map(lambda x : table_slot[x], range(1,6)))
    for x in map(lambda r : r[2][0:2] + ':' + r[2][2:4],
            filter(lambda r : "SER" in r[1] and (r[0] != stoday if day_selector
                                            else r[0] == stoday),  
            map(lambda sr : sr.split('*'), 
            res.split('^')[:-1]))):
        pres.remove(x)
    return list(map(_adjust_slot, pres))

def _reserve(driver, repr_slot, verbose = True):
    tres = table_res[repr_slot]
    try:
        repf = query2(driver, "aulefree", 
            {'v1':str(_adjust_slot(repr_slot)), 'v2': tres["edificio"] })
        freeseats = next(filter(
            lambda sl: tres["aula"] in sl, repf.split('*'))).split('^')[-1]
        param = {
            "v1" : str(_adjust_slot(repr_slot)),
            "v2" : tres["edificio"],
            "v3" : '^'.join([tres["aula"], tres["id"], freeseats])
        }
        rep = query2(driver, "prenota", param)
    except:
        rep = "OUT"
    finally:
        if (rep == "OK"):
            print(f">>> succeeded {tres['repr']}")
            return True
        elif (rep == "OUT"):
            print(f">>> full-fail {tres['repr']}") if verbose \
                                                   else print(".", end='', flush = True)
        return False

def _create(driver, repr_slot):
    tm = datetime.today() + timedelta(days=(1 if day_selector else 0))
    param = {
        "v1" : '*'.join([tm.strftime("%Y%m%d"), table_res[repr_slot]['id'], 
        repr_slot[:2] + repr_slot[3:],])
    }
    rep = query2(driver, "godel", param)
    if (rep != "OK"):
        print(f">>> create-failed {table_res[repr_slot]['repr']}")
    return driver, repr_slot

def reserve(driver, create = False):
    foreach(1)(compose(_reserve, _create if create else lambda *x : x)) \
        (driver, parse_argslot(driver))

def _access2(driver, repr_slot):
    rep = query2(driver, "qr", { 'bc' : table_res[repr_slot]['code'] })
    res_string = '*'.join(next(filter(lambda r: r[2] == repr_compact(repr_slot), 
        map(lambda r: r.split('*'), rep.split('^')[:-1]))))
    rep2 = query2(driver, "accedi", { 'v1' : res_string })
    if rep2 in ["CANCELLATA"]:
        print(f">>> access-failed {repr_slot}")
    print(f">>> access-succeded {repr_slot}")

def access(driver):
    qry = query2(driver, "mypren", { })

    stoday = datetime.today().strftime("%Y%m%d")
    qres = list(filter(lambda r: table_res[repr_lengthy(r[2])]['id'] == r[1] and
            (r[0] != stoday if day_selector else r[0] == stoday),
        sorted(map(lambda r: r.split('*'),
            qry.split('^')[:-1]), key=lambda r : int(r[2]))))
    acc_res = list(filter(lambda r: r[5] == 'PREN' and
        datetime.now() < datetime.today().replace(hour=int(r[2][:2]) + 3, minute=0), qres))
    [schedule.today(hour = int(s[:2]) - 1, minute = 0, second = 0)(_access2)(driver, s) \
        for s in map(lambda r: repr_lengthy(r[2]), acc_res)]

loginw = requires([username, password])(
    schedule.today(hour=21, minute=58, second=0)(login))
reservew = schedule.today(hour=22, minute=0, second=0)(reserve)

@foreach(1)
def display_free(driver, repr_slot):
    idx_slot = _adjust_slot(repr_slot)
    rep = query2(driver, "aulefree", {'v1':str(idx_slot), 'v2':'ED1' })
    print(f"display-slot {repr_slot}")
    for r in rep[1:].split('*'):
        print(r.split('^')) 

def hammer_custom(driver, repr_slot, ts, delta): 
    cycle.next(delta=delta, hour=ts[0], minute=ts[1], second=ts[2])(
        lambda : _reserve(driver, repr_slot, False)) ()

def_cond = lambda ls : len(ls) == 0
def hammer_spread(driver, repr_list, 
        exit_cond = def_cond, tm_thres = None, on_reserve = lambda _: 0):
    print(f"missing-reservations {repr_list}")
    @multiple( [ cycle.next(delta = d, hour = h, minute = m, second = 0) 
        for h in [int(s[:2]) for s in repr_list] 
        for d,m in [(90, 0), (20, 19), (5, 20), (3, 25)] ]
    ) 
    def run():
        ids_list = list(repr_list)
        for x in ids_list:
            if _reserve(driver, x, False):
                repr_list.remove(x)
                on_reserve(x)

        return exit_cond(ids_list) or \
            (datetime.now() > tm_thres if tm_thres != None else False)
    
    run()
    return repr_list

# add required_slots argument
def auto(driver, repr_list):
    ts = Tasker()
    
    def sched_access(slot, day_method):
        ts.append(_access2, getattr(Tasker, day_method)(
            hour = int(slot[:2]) - 1, minute = 0, second = 0),
            args=(driver, slot))

    def phase1():
        foreach(1)(_reserve)(driver, parse_argslot(driver))
        phase2(datetime.today() + timedelta(days = 1), "tomorrow")

    def phase2(day, day_method):
        qry = query2(driver, "mypren", { })
        qres = list(filter(lambda r: table_res[repr_lengthy(r[2])]['id'] == r[1] 
            and r[0] == day.strftime("%Y%m%d"),
            sorted(map(lambda r: r.split('*'),
                qry.split('^')[:-1]), key=lambda r : int(r[2]))))

        acc_res = list(filter(lambda r: r[5] == 'PREN' and 
            datetime.now() < day.replace(hour=int(r[2][:2]), minute=20), qres))
        missing_res = [s for s in repr_list if s not in map(lambda r: repr_lengthy(r[2]), qres) and 
            datetime.now() < day.replace(hour=int(s[:2]) + 3, minute=0)]

        for r in acc_res:
            sched_access(repr_lengthy(r[2]), day_method)

        if len(missing_res) == 0: return
        for s in [table_slot[x] for x in range(1,5)]:
            def run1(driver, running_slot = None):
                if len(missing_res) == 0: return
                hammer_spread(driver, missing_res, # exit_cond = lambda ls: r not in ls, 
                    tm_thres = Tasker.next(hour = int(running_slot[:2]) - 1, minute=0, second=0),
                    on_reserve = lambda s: sched_access(s, day_method))

            def run2(driver, running_slot = None, target_slot = None):
                if len(missing_res) == 0: return
                hammer_spread(driver, missing_res, exit_cond = lambda ls: target_slot not in ls, 
                    tm_thres = Tasker.next(hour = int(running_slot[:2]), minute=25, second=0),
                    on_reserve = lambda s: sched_access(s, day_method))
                if target_slot in missing_res:
                    compose(_reserve, _create)(driver, target_slot) 
                    missing_res.remove(target_slot)
                    _access2(driver, target_slot)

            ts.append(run1, getattr(Tasker, day_method)(hour = int(s[:2]) - 3, minute = 0, second = 0),
                    kwargs={ 'running_slot' : s }, args=( driver, )) 
            ts.append(run2, getattr(Tasker, day_method)(hour = int(s[:2]) - 1, minute = 0, second = 1),
                    kwargs={ 'running_slot' : s, 'target_slot' : missing_res[0] }, args=( driver, )) 

    phase2(datetime.today(), "today")
    # ts.append(phase0, Tasker.today(hour = 21, minute = 58, second = 0), kwargs={ }, args=( ))
    ts.append(phase1, Tasker.today(hour = 22, minute = 0, second = 0), kwargs={ }, args=( ))
    ts()

def parse_argslot(driver):
    if not args.slot[0][1].isdigit():
        return map(lambda x : table_slot[x], _missing_res(driver)) \
            if 'missing' == args.slot[0] \
            else map(lambda x : table_slot[x], [8, 7, 9, 6, 10]
                [0:4 if args.slot[0] == 'day' else 5])
    return args.slot

def init(headless):
    options = Options()
    options.headless = headless
    return webdriver.Firefox(options=options)

def sigint_handler(sig, frame):
    if sig == signal.SIGINT:
        suspend_sleeper.shutdown()
        print("\n", end='')
        exit(0)
signal.signal(signal.SIGINT, sigint_handler)

import argparse
parser = argparse.ArgumentParser(description='s4a-bot')

parser.add_argument(
    'action', nargs='*', choices = ['login', 'reserve', 'access', 'hammer-slot', 
        'hammer-custom', 'hammer-spread', 'display', 'default', 'auto'],
    default = 'default')
parser.add_argument('-wh', '--with-head', default=False, action="store_true")
parser.add_argument('-l', '--delayed', default=False, action="store_true")
parser.add_argument('-c', '--create', default=False, action="store_true")
parser.add_argument('-s', '--slot', nargs='*',
     choices=["08:00", "11:00", "14:00", "17:00", 
         "20:00", "all", "day", "missing"], default=["day"])
parser.add_argument('-d', '--delta', type=int, default=20)
parser.add_argument('-t', '--time', type=ascii, default="00:00:00")
# --time must be passed in the format hh:mm:ss

args = parser.parse_args()
driver = init(headless = (not args.with_head) and 
    ('login' not in args.action))

if 'default' in args.action:
    print("default-reserve")
    reservew(loginw(driver))
elif 'reserve' in args.action:
    print("reserve")
    reservep = reservew if args.delayed else reserve
    reservep(loginw(driver) if args.delayed 
                            else login(driver), create = args.create)
elif 'login' in args.action:
    print("plain-login")
    login(driver)
    args.with_head = True
elif 'hammer-slot' in args.action:
    print("hammer-slot")
    # hammer --slot 11:00
    hammer_spread(login(driver), (args.slot[0],))
elif 'hammer-custom' in args.action:
    # hammer-custom --slot 14:00 --time 15:50:01 --delta 20
    print("hammer-custom")
    tm = list(map(int, args.time[1:-1].split(':')))
    hammer_custom(login(driver), parse_argslot(driver)[0], tm, args.delta)
elif 'hammer-spread' in args.action:
    print("hammer-spread")
    # hammer-spread --slot day
    hammer_spread(login(driver), list(parse_argslot(driver)))
elif 'auto' in args.action:
    print("mf-auto")
    # auto --slot day
    auto(login(driver), list(parse_argslot(driver)))

if 'display' in args.action:
    display_free(login(driver) if driver.current_url == 'about:blank'
                               else driver, parse_argslot(driver))
if 'access' in args.action:
    print("access")
    access(login(driver) if driver.current_url == 'about:blank' else driver)
    
suspend_sleeper.shutdown()

import sys
if not sys.flags.interactive:
    if args.with_head:
        print("done", end='')
        input()
    else:
        print("done")
    driver.close()
else:
    print("done")
