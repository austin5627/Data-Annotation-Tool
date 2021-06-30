import math
import os
import time
from sys import platform

import PySimpleGUI as sg
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import vlc
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk as Toolbar
from matplotlib.patches import Rectangle

plt.style.use('dark_background')
plt.rcParams['keymap.all_axes'].remove('a')
plt.rcParams.update({
    "figure.facecolor": "#2B2B28",
    "axes.facecolor": "#2B2B28",
})


def draw_figure(canvas, figure, canvas_toolbar):
    if canvas.children:
        for child in canvas.winfo_children():
            child.destroy()
    if canvas_toolbar.children:
        for child in canvas_toolbar.winfo_children():
            child.destroy()
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    toolbar = Toolbar(figure_canvas_agg, canvas_toolbar)
    toolbar.config(background='#E3B04B',)
    for button in toolbar.winfo_children():
        button.config(background='#E3B04B')
    toolbar.update()
    figure_canvas_agg.get_tk_widget().pack(side="top", fill="both", expand=1)


def update_line(num, line, last):
    global curr_sample, curr_time, last_time

    if curr_sample >= len(data) or curr_time >= player.get_length():
        toggle_animation(line_anim, True)
        return line

    if last != 0:
        last_time = time.time()

    time_elapsed = time.time() - last_time
    last_time = time.time()

    if auto_scroll:
        scale = plt.xlim()[1] - plt.xlim()[0]
        plt.xlim([curr_sample - scale / 2, curr_sample + scale / 2])

    curr_string = f'Current Time: {int(curr_time):<5,} ' \
                  f'Current Sample: {int(curr_sample):<4,}' \
                  f' Values: ('
    for d in data.columns:
        if curr_sample >= 0:
            curr_string += f'{d}:{data[d][int(curr_sample)]}, '
    curr_string = curr_string[:-2] + ')'
    window['-CURRENT-'].update(curr_string)

    if len(sync) >= 1 or last != 0:
        real_sample_rate = time_elapsed * player.get_rate() * sample_rate
        line.set_data([curr_sample, curr_sample], [-3000, 3000])
        curr_sample += real_sample_rate

    curr_time += player.get_rate() * time_elapsed * 1000

    if labeling != -1:
        live_label()

    return line,


def live_label():
    start = label_list[labeling][0][0]
    rect = label_list[labeling][1][0]
    text = label_list[labeling][1][1]
    rect.set_width(int(curr_sample) - start)
    text.set_x(min(start, curr_sample))
    label_list[labeling][0][1] = int(curr_sample)


def make_label(start, end, label):
    start = int(start)
    end = int(end)
    rect = Rectangle((start, -4000), end - start, 8000, edgecolor='black', facecolor='grey', alpha=.5)
    plt.gca().add_patch(rect)
    text = plt.text(min(start, end), 0, label)
    label_list.append([[start, end], [rect, text], label])
    plt.draw()
    return len(label_list) - 1


def remove_label(x=None):
    for label_element in label_list[:]:
        label_element[0].sort()
        if x is None or label_element[0][0] <= x <= label_element[0][1]:
            for e in label_element[1]:
                e.remove()
            label_list.remove(label_element)


def toggle_animation(animation, state):
    global running, last_time
    running = state
    if running:
        player.pause()
        animation.pause()
    else:
        player.play()
        animation.resume()
        update_line(0, seek_line, 1)
    running = not running
    window['-StartStop-'].update(text=['Play', 'Pause'][running])


clk_line = plt.axvline(0)


def on_click(event):
    global coords, labeling

    x, y = event.xdata, event.ydata
    if x is None or y is None:
        return
    x = math.floor(x)
    y = math.floor(y)
    coords = (x, y)
    if event.dblclick:
        clk_line.set_data([x, x], [0, 1])
        plt.draw()
        if event.button == 1:
            select_label = window['-LabelList-'].get()
            if len(select_label):
                make_label(curr_sample, coords[0], select_label[0])
        elif event.button == 3:
            remove_label(coords[0])
        labeling = -1
    elif event.button == 2:
        jump_to(jump_sample=x)


def load_file(file_name):
    global curr_sample, curr_time, data_file, sync
    data_file = 'temp.txt'
    save_labels()
    data_file = file_name
    new_data = pd.read_csv(DATA_DIR + file_name)
    if os.path.exists(VIDEOS_DIR + file_name[:-4] + '-sync.txt'):
        sync = pd.read_csv(VIDEOS_DIR + file_name[:-4] + '-sync.txt', names=['time', 'sample']).values.tolist()
        window['-SyncTab-'].update(values=sync)
    else:
        sync = []
        window['-SyncTab-'].update(values=sync)

    new_media = inst.media_new(VIDEOS_DIR + file_name[:-4] + '-video.mp4')
    player.set_media(new_media)
    player.play()
    window.finalize()
    window['-DataList-'].update(values=new_data.columns)
    for i in lines.values():
        i.remove()
    lines.clear()
    remove_label()
    fig.canvas.draw()
    curr_sample=0
    player.pause()
    jump_to(jump_time=0)
    load_labels(file_name)
    return new_data


def save_labels():
    annotations_filename = data_file[:-4] + '-annotations.txt'

    sorted_labels = sorted(label_list, key=lambda x: (x[0][0], x[0][1]))

    with open(LABELS_DIR + annotations_filename, 'w') as annotations_file:
        for label in sorted_labels:
            label[0].sort()
            label_line = str(label[0][0]) + ' - ' + str(label[0][1]) + ', ' + label[2] + '\n'
            annotations_file.write(label_line)


def load_labels(file_name):
    if os.path.exists(LABELS_DIR + file_name[:-4] + '-annotations.txt'):
        with open(LABELS_DIR + file_name[:-4] + '-annotations.txt', 'r') as annotations_file:
            for label_line in annotations_file:
                l_range, label = label_line.split(', ')
                if label[-1] == '\n':
                    label = label[:-1]
                start, end = l_range.split('-')
                if len(label):
                    make_label(start, end, label)


def jump_to(jump_time=-1, jump_sample=-1):
    global curr_sample, curr_time

    if jump_sample == -1:
        if len(sync) >= 1:
            sync_point = sync[0]
            jump_sample = int((jump_time-sync_point[0]) * sample_rate / 1000) + sync_point[1]
        else:
            jump_sample = curr_sample
    elif jump_time == -1:
        if len(sync) >= 1:
            sync_point = sync[0]
            jump_time = int((jump_sample-sync_point[1]) * 1000 / sample_rate) + sync_point[0]
        else:
            jump_time = curr_time
    if jump_time < 0:
        jump_to(jump_time=0)
        return

    curr_sample = jump_sample
    curr_time = jump_time
    player.set_time(int(jump_time))
    if labeling != -1:
        live_label()
    update_line(0, seek_line, 1)
    plt.draw()


sg.theme('DarkGrey2')

# Set Size of graph and video
fig_width, fig_height = 1500, 300
video_width, video_height = 1500, 400

# Video Column Layout
fig_column = sg.Column(
    layout=[
        [sg.Image('', size=(video_width, video_height), key='-VidOut-')],
        [sg.Canvas(key='-FigureCanvas-', size=(fig_width, fig_height))],
        [
            sg.Button('Save Labels', key='-SaveButton-', size=(12, 1)),
            sg.ButtonMenu('Speed', ['Menu', ['1x', '2x']], key='-Speed-'),
            sg.Button('<<5s', key='-5Sec--'), sg.Button('<1s', key='-1Sec--'),
            sg.B('Play', key='-StartStop-'),
            sg.Button('1s>', key='-1Sec+-'), sg.Button('5s>>', key='-5Sec+-'),
            sg.Checkbox('Auto Scroll', enable_events=True, key='-AutoScroll-'),
            sg.Canvas(key='-ControlsCanvas-'),
        ],
        [sg.Text('Current Sample:0 Values:', key='-CURRENT-', size=(150, 1))],
    ],
    pad=(0, 0),
    key='-FigColumn-'
)

DATA_DIR = 'data/'
VIDEOS_DIR = 'videos/'
LABELS_DIR = 'labels/'

files = [os.fsdecode(f) for f in os.listdir(DATA_DIR)]
data_file = files[0]
data = pd.read_csv(DATA_DIR + data_file)
labels = pd.read_csv(LABELS_DIR + 'labels.txt', names=['']).values.flatten().tolist()
# Data column layout
# noinspection PyTypeChecker
data_column = sg.Column(
    layout=[
        [sg.Listbox(values=files, key='-FileList-', size=[30, 10])],
        [sg.Button('Load Selected File', key='-LoadButton-')],
        [sg.Listbox(values=data.columns, key='-DataList-', size=[30, 10],
                    select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE, enable_events=True)
         ],
        [sg.Listbox(values=labels, key='-LabelList-', size=[30, 10])],
        [sg.InputText(key='-Time-', size=(10, 1)),
         sg.Button('Jump To Time(ms)', key='-JumpTime-', size=(15, 1))
         ],
        [sg.InputText(key='-Sample-', size=(10, 1)),
         sg.Button('Jump To Sample', key='-JumpSample-', size=(15, 1))
         ],
        [sg.InputText(key='-SyTime-', tooltip='Sync Time', size=(4, 1)),
         sg.InputText(key='-SySample-', tooltip='Sync Sample', size=(4, 1)),
         sg.Button('Add Sync Point', key='-Sync-', size=(15, 1))
         ],
        [sg.Table(key='-SyncTab-', headings=['Time', 'Sample'],
                  values=[[' ', ' ']],
                  select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                  num_rows=4,
                  col_widths=[12,12],
                  auto_size_columns=False),
         ],
        [sg.Button('Delete Sync', key='-DSync-', size=(12, 1))],
    ],
    vertical_alignment='top',
    key='-DATA_COLUMN-'
)

# Define the window layout
layout = [
    [data_column, fig_column],
]

window = sg.Window("Labeling Application", layout, return_keyboard_events=True, finalize=True, resizable=True)
window.maximize()

# Create Video Player
inst = vlc.Instance()
player = inst.media_player_new()
media = inst.media_new(VIDEOS_DIR + files[0][:-4] + '-video.mp4')
player.set_media(media)
if platform.startswith('linux'):
    player.set_xwindow(window['-VidOut-'].Widget.winfo_id())
else:
    player.set_hwnd(window['-VidOut-'].Widget.winfo_id())

player.play()

fps = 1

plt.figure(1)

plt.legend()
fig = plt.gcf()
DPI = fig.get_dpi()
# hovers over the figure, it's close to canvas size
fig.set_size_inches((fig_width + 4) / float(DPI), (fig_height + 4) / float(DPI))
fig.canvas.mpl_connect('button_press_event', on_click)
plt.axis([0, 200, -1000, 3000])
coords = (0, 0)

auto_scroll = False
running = False
curr_sample = 0
curr_time = 0
labeling = -1
last_time = time.time()
lines = {}

seek_line = plt.axvline(1, color='r')
label_list = []

sample_rate = 20
sync = []
interval = 20
line_anim = animation.FuncAnimation(fig, update_line, 100, fargs=(seek_line, 0,), interval=interval)
# noinspection PyTypeChecker
draw_figure(window["-FigureCanvas-"].TKCanvas, fig, window['-ControlsCanvas-'].TKCanvas)
line_anim.pause()

player.pause()
player.set_time(0)

while True:
    event, values = window.read()
    if event == sg.TIMEOUT_KEY:
        continue

    # print(event)

    if event == '-DataList-':
        window['-FigureCanvas-'].set_focus()
        selected = window['-DataList-'].get()
        for d in data.columns:
            if d in selected and d not in lines and data[d].dtype in [np.int64, np.float64]:
                lines[d], = plt.plot(data[d], label=d)
                plt.legend()
            elif d not in selected and d in lines:
                lines.pop(d).remove()
                plt.legend()
        fig.canvas.draw()

    if event == '-AutoScroll-':
        auto_scroll = values['-AutoScroll-']

    if event in ['-StartStop-', ' ']:
        window['-FigureCanvas-'].set_focus()
        toggle_animation(line_anim, running)

    if event == '-LoadButton-':
        toggle_animation(line_anim, True)
        new_file = values['-FileList-']
        if len(new_file):
            data = load_file(new_file[0])

    if event == '-JumpTime-' and values['-Time-'].isnumeric():
        window['-ControlsCanvas-'].set_focus()
        jump_to(jump_time=int(values['-Time-']))

    if event == '-JumpSample-' and values['-Sample-'].isnumeric():
        window['-ControlsCanvas-'].set_focus()
        jump_to(jump_sample=int(window['-Sample-'].get()))

    if event == '-Sync-':
        sync_time, sync_sample = curr_time, curr_sample
        if values['-SyTime-']:
            sync_time = int(values['-SyTime-'])
        if values['-SySample-']:
            sync_sample = int(values['-SySample'])
        sync.append([int(sync_time), int(sync_sample)])
        window['-SyncTab-'].update(values=sync)
        if len(sync) >= 2 and sync[0] != sync[1]:
            sample_rate = (sync[1][1] - sync[0][1]) / (sync[1][0] - sync[0][0]) * 1000
        with open(VIDEOS_DIR + data_file[:-4] + '-sync.txt', 'w') as sync_file:
            for sy in sync:
                sync_file.write(str(sy[0]) + ', ' + str(sy[1]))
        jump_to(jump_time=curr_time)

    if event == '-DSync-' and values['-SyncTab-']:
        row = values['-SyncTab-'][0]
        sync.pop(row)
        window['-SyncTab-'].update(values=sync)

    if event == '-SaveButton-':
        save_labels()

    if event == '-Speed-':
        speed_values = {'3x': 3,
                        '2x': 2,
                        '1x': 1}
        player.set_rate(speed_values[values['-Speed-']])

    if window.FindElementWithFocus() in [window['-Time-'],
                                         window['-Sample-'],
                                         window['-SyTime-'],
                                         window['-SySample-']]:
        continue

    if event in ['-5Sec+-', 'Right:39']:
        jump_to(jump_time=curr_time + 5000)
    if event in ['-5Sec--', 'Left:37']:
        jump_to(jump_time=curr_time - 5000)
    if event in ['-1Sec+-', '.']:
        jump_to(jump_time=curr_time + 1000)
    if event in ['-1Sec--', ',']:
        jump_to(jump_time=curr_time - 1000)

    if event in [str(i) for i in range(10)]:
        if labeling == -1:
            l_num = make_label(curr_sample, curr_sample, labels[int(event)-1])
            labeling = l_num
        else:
            labeling = -1
    if event == '\t':
        if labeling == -1:
            select_label = window['-LabelList-'].get()
            if len(select_label):
                l_num = make_label(curr_sample, curr_sample, select_label[0])
                labeling = l_num
        else:
            labeling = -1

    if event == sg.WIN_CLOSED:
        data_file = 'temp.txt'
        save_labels()
        break

window.close()
