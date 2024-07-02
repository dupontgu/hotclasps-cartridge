import board
import rp2pio
import adafruit_pioasm
import time
import array
import gc
import os
import alarm
from digitalio import DigitalInOut, Direction, Pull

# Audio output PIO
# output each sample as PWM
# MSB determines which of 2 pins the PWM is routed
hc_output = """
.program hc_output
pull
mov isr, osr
start:
    jmp !osre main_loop
    pull
main_loop:
    mov x, y
    mov y, isr
    set pins, 0b11
    out x, 1
    jmp !x pos_pulse
    out x, 7
neg_loop:
    jmp x!=y neg_skip
    set pins, 0b010
neg_skip:
    jmp y-- neg_loop
    jmp start
pos_pulse:
    out x, 7
pos_loop:
    jmp x!=y pos_skip
    set pins, 0b001
pos_skip:
    jmp y-- pos_loop
    jmp start
"""

audio_state_machine = None  

BUFF_SIZE = 16384 * 2
NUM_CHUNKS = 32
SLEEP_THRESHOLD = 800

btn = DigitalInOut(board.PLAY_BTN)
btn.direction = Direction.INPUT
btn.pull = Pull.UP

dbg = DigitalInOut(board.DBG)
dbg.direction = Direction.OUTPUT

woken_from_sleep = alarm.wake_alarm is not None

# blink the debug led [err_code] number of times, repeatedly to signal a "crash"
def die(err_code):
    global dbg
    while True:
        for i in range(err_code):
            dbg.value = True
            time.sleep(0.15)
            dbg.value = False
            time.sleep(0.15)
        time.sleep(1)

sounds_dir = "sounds"

if not sounds_dir in os.listdir():
    die(4)

sounds = []
for s in os.listdir(sounds_dir):
    # don't play hidden files - macos likes to add junk files if you drag/drop from finder
    if (s[0] != '.'):
        print(s)
        sounds.append(sounds_dir + "/" + s)

sounds.sort()
sound_count = len(sounds)
if sound_count == 0:
    die(3)
sound_index = 0

# VERY IMPORTANT
# garbage colletor might run during playback if not disabled and cause gaps
# since we are tightly managing an fixed-size audio buffer, disable and manage manually
gc.disable()

# instantiate audio buffer, and create a chunked "view" into it to make writing easier
# chunks let us do more frequent background writes to PIO
read_buf = bytearray(BUFF_SIZE)
mv = memoryview(read_buf)
chunks = []
chunk_size = int(BUFF_SIZE / NUM_CHUNKS)
for i in range(NUM_CHUNKS):
    chunks.append(mv[i * chunk_size : ((i+1) * chunk_size)])
fifo_wrap = array.array('L', b"\x7f\x00\x00\x00")

debounce_reset = True

def init_sm():
    global audio_state_machine
    if audio_state_machine:
        audio_state_machine.stop()
        audio_state_machine.deinit()
    audio_state_machine = rp2pio.StateMachine(
        program = adafruit_pioasm.assemble(hc_output),
        frequency = 25100000,
        first_set_pin=board.AUDIO_P,
        initial_out_pin_direction=0b11,
        out_shift_right=False,
        initial_set_pin_state = 0b0000,
        set_pin_count = 2,
    )   
    audio_state_machine.restart()
    audio_state_machine.write(fifo_wrap)

# poll if user is pressing the button to stop the audio
def check_for_stop():
    global debounce_reset
    if not debounce_reset and btn.value:
        debounce_reset = True
    if (not btn.value and debounce_reset):
        print("stopping..")
        audio_state_machine.stop()
        while not btn.value:
            time.sleep(0.05)
            pass
        return True
    return False

def debug_blink(times):
    for _ in range(times):
        dbg.value = True
        time.sleep(0.10)
        dbg.value = False
        time.sleep(0.10)

while True:
    sleep_counter = 0
    sound = sounds[sound_index]
    sound_index = (sound_index + 1) % sound_count
    print(f'loading {sound}')
    debug_blink(1 if woken_from_sleep else 2)
    with open(sound,'rb') as fp:
        # once sound is ready, wait for user to hit play button
        # if `woken_from_sleep`, we know that they have already pressed it
        # if they dont press by `SLEEP_THRESHOLD`, go to sleep
        while btn.value and not woken_from_sleep:
            sleep_counter += 1
            if sleep_counter >= SLEEP_THRESHOLD:
                sleep_counter = 0
                btn.deinit()
                time.sleep(0.3)
                btn_pin = alarm.pin.PinAlarm(pin=board.PLAY_BTN, value=False, edge=True, pull=True)
                time.sleep(0.3)
                alarm.exit_and_deep_sleep_until_alarms(btn_pin)
            time.sleep(0.01)
            pass
        init_sm()
        woken_from_sleep = False
        debounce_reset = False
        print("playing")
        ## multiple blank writes to ensure followups are properly queued.
        for _ in range(3):
            audio_state_machine.background_write(read_buf)
        while True:
            should_break = False
            for c in chunks:
                data = fp.readinto(c, chunk_size)
                if (not data or check_for_stop()):
                    should_break = True
                    audio_state_machine.restart()
                    break
                time.sleep(0.04)
            if (should_break):
                break
            audio_state_machine.background_write(read_buf)
        gc.collect()