"""
Editor stuff

        self._editable = [
            ("position", (self.x, self.y),  (int, int)),
            ("anchor", (self.ax, self.ay), (int, int)),
            ("interact", self.interact, str),
            ("allow_draw", self._allow_draw, bool), # ( "allow_update", "allow_use", "allow_interact", "allow_look"]
            ]
"""
import subprocess
import threading
import glob

try:
    import tkinter as tk
    import tkinter.filedialog as tkfiledialog
    import tkinter.simpledialog as tksimpledialog
    import tkinter.messagebox as tkmessagebox

    EDITOR_AVAILABLE = True
except ImportError:
    tk = None
    tkfiledialog = None
    tksimpledialog = None
    tkmessagebox = None
    EDITOR_AVAILABLE = False


from .constants import *
from .utils import *
from .emitter import Emitter
from .motionmanager import MotionManager
from .menumanager import MenuManager
from .menufactory import MenuFactory
from .actor import Actor, Item
from .camera import Camera
from .portal import Portal
from .scene import Scene
from .walkareamanager import WalkAreaManager


def open_editor(game, filepath, track=True):  # pragma: no cover
    """
        Open a text editor to edit fname, used by the editor when editing
        scripts

        track -- add to game.script_modules for tracking and reloading
    """
    editor = os.getenv('EDITOR', DEFAULT_TEXT_EDITOR)

    if track:
        # add to the list of modules we are tracking
        module_name = os.path.splitext(os.path.basename(filepath))[0]
        if module_name not in game.script_modules and module_name != "__init__":
            print("ADDING %s TO MODULES" % module_name)
            game.script_modules[module_name] = 0
            # add file directory to path so that import can find it
            if os.path.dirname(filepath) not in sys.path:
                sys.path.append(os.path.dirname(filepath))

    if sys.platform.startswith('darwin'):
        subprocess.call(('open', filepath))
    elif os.name == 'nt':
        os.startfile(filepath)
    elif os.name == 'posix':
        subprocess.call(('xdg-open', filepath))


# pyqt4 editor


def edit_object_script(game, obj):  # pragma: no cover
    """ Create and/or open a script for editing """
    directory = obj._directory
    fname = os.path.join(directory, "%s.py" % slugify(obj.name).lower())
    if not os.path.isfile(fname):  # create a new module for this actor
        with open(fname, "w") as f:
            f.write(
                "from pyvida import gettext as _\nfrom pyvida import answer\nfrom pyvida import set_interacts, BOTTOM\n\n")
    module_name = os.path.splitext(os.path.basename(fname))[0]

    # find and suggest some missing functions (interact, look, use functions)
    with open(fname, "r") as f:
        script = f.read()
    slug = slugify(obj.name).lower()
    search_fns = ["def interact_%s(game, %s, player):" % (
        slug, slug), "def look_%s(game, %s, player):" % (slug, slug),
                  "def use_on_%s_default(game, %s, obj):" % (slug, slug),
                  "def use_%s_on_default(game, obj, %s):" % (slug, slug),
                  ]
    if not isinstance(obj, Portal) and game.player:
        for i in list(game.get_player().inventory.keys()):
            slug2 = slugify(i).lower()
            search_fns.append("def %s_use_%s(game, %s, %s):" %
                              (slug, slug2, slug, slug2))
    with open(fname, "a") as f:
        for fn in search_fns:
            if fn not in script:
                f.write("#%s\n#    pass\n\n" % fn)
    open_editor(game, fname)
    __import__(module_name)


def edit_action_motion(game, obj, action):  # pragma: no cover
    directory = obj._directory
    fname = os.path.join(directory, "%s.motion" % slugify(action.name).lower())
    if not os.path.isfile(fname):  # create a new module for this actor
        with open(fname, "w") as f:
            f.write(
                "#first line of this file is metadata, some combination of:\n")
            f.write("#x,y,z,r,scale\n")
    open_editor(game, fname, track=False)


def set_edit_object(game, obj, old_obj):  # pragma: no cover
    obj = get_object(game, obj)
    old_obj = get_object(game, old_obj)
    if old_obj:
        old_obj.show_debug = False
    if obj._editable == [] and hasattr(obj, "set_editable"):
        obj.set_editable()
    obj.show_debug = True


def editor_new_object(game, obj):  # pragma: no cover
    d = os.path.join(get_smart_directory(game, obj), obj.name)
    if not os.path.exists(d):
        os.makedirs(d)
    obj.smart(game)
    obj.load_assets(game)
    obj.x, obj.y = (
        game.resolution[0] / 2, game.resolution[1] / 2)
    game.add(obj)
    game.get_scene().add(obj)


if log:
    log.info("CHECKING FOR EDITOR")

if EDITOR_AVAILABLE:  # pragma: no cover
    if log: log.info("EDITOR AVAILABLE")


    class SelectDialog(tksimpledialog.Dialog):

        def __init__(self, game, title, objects, *args, **kwargs):
            parent = tk._default_root
            self.game = game
            self.objects = objects
            super().__init__(parent, title)

        def body(self, master):
            self.listbox = tk.Listbox(master)
            self.listbox.pack()
            objects = [i.name for i in self.objects if i.name != None]
            objects.sort()
            for item in objects:
                self.listbox.insert(tk.END, item)
            return self.listbox  # initial focus

        def apply(self):
            self.result = self.listbox.selection_get()


    class SceneSelectDialog(SelectDialog):

        def __init__(self, game, title, *args, **kwargs):
            objects = game.scenes.values()
            super().__init__(game, title, objects, *args, **kwargs)


    class SceneOptionMenu(tk.OptionMenu):

        def __init__(self, group, tkvalue, *args, **kwargs):
            self._group = group
            self._tkvalue = tkvalue
            super().__init__(group, tkvalue, *args, **kwargs)

        pass


    class ObjectSelectDialog(SelectDialog):

        def __init__(self, game, title, *args, **kwargs):
            objects = list(game.actors.values()) + list(game.items.values())
            super().__init__(game, title, objects, *args, **kwargs)


    class MyTkApp(threading.Thread):

        def __init__(self, game):
            threading.Thread.__init__(self)
            self.game = game
            if len(self.game.get_scene().objects) > 0:
                self.obj = get_object(game, self.game.get_scene().objects[0])
            else:
                self.obj = None
            #        self.obj = list(self.game.get_scene().objects.values())[0] if len(self.game.get_scene().objects.values())>0 else None
            if self.obj:
                self.obj.show_debug = True
            self.rows = 0
            self.index = 0
            self.start()
            self.scene = None  # self.game.scene
            self.editor_label = None

        def set_edit_object(self, obj):
            set_edit_object(self.game, obj, self.obj)

            self.obj = obj
            if self.editor_label:
                self.editor_label.grid_forget()
                self.editor_label.destroy()
            #            self.editor_label["text"] = obj.name
            self.create_editor_widgets()

        #            self.edit_button["text"] = obj.name

        def create_navigator_widgets(self):
            row = self.rows
            group = tk.LabelFrame(self.app, text="Navigator", padx=5, pady=5)
            group.grid(padx=10, pady=10)

            self.scene = tk.StringVar(group)

            def change_scene(*args, **kwargs):
                sname = args[0]
                if self.game.editing and self.game.editing.show_debug:
                    self.game.editing.show_debug = False
                new_scene = get_object(self.game, sname)
                self.app.objects = objects = new_scene.objects
                self.game.camera.immediate_scene(new_scene)
                # new_scene.load_assets(self.game)
                self.index = 0
                if len(objects) > 0:
                    self.game.editing = get_object(self.game, objects[self.index])
                    self.game.editing.show_debug = True
                self.game.get_player().relocate(new_scene)

            def refresh(selector):
                # objects = self.game.scenes.values()
                menu = selector["menu"]
                menu.delete(0, "end")
                scenes = [x.name for x in self.game.scenes.values()]
                scenes.sort()
                for value in scenes:
                    menu.add_command(
                        label=value, command=tk._setit(self.scene, value, change_scene))

            tk.Label(group, text="Current scene:").grid(column=0, row=row)
            scenes = [x.name for x in self.game.scenes.values()]
            scenes.sort()
            self._sceneselect = SceneOptionMenu(
                group, self.scene, *scenes, command=change_scene)
            self._sceneselect.grid(column=1, row=row)

            #        actors = [x.name for x in self.game.actors.values()]
            #        actors.sort()
            #        option = tk.OptionMenu(group, self.game.scene, *scenes, command=change_scene).grid(column=1,row=row)

            def _new_object(obj):
                editor_new_object(self.game, obj)

                self.app.objects = self.game.get_scene().objects
                self.set_edit_object(obj)

            def add_object():
                d = ObjectSelectDialog(self.game, "Add to scene")
                if not d:
                    return
                obj = get_object(self.game, d.result)
                if obj == None:
                    return
                if not obj:
                    tkmessagebox.showwarning(
                        "Add Object",
                        "Unable to find %s in list of game objects" % d.result,
                    )
                obj.load_assets(self.game)
                if obj.clickable_area.w == 0 and obj.clickable_area.h == 0:
                    obj.guess_clickable_area()
                self.game.get_scene().immediate_add(obj)
                self.set_edit_object(obj)

            def new_actor():
                d = tksimpledialog.askstring("New Actor", "Name:")
                if not d:
                    return
                _new_object(Actor(d))

            def new_item():
                d = tksimpledialog.askstring("New Item", "Name:")
                if not d:
                    return
                _new_object(Item(d))

            def new_portal():
                d = SceneSelectDialog(self.game, "Exit Scene")
                if not d:
                    return
                name = "{}_to_{}".format(self.game.get_scene().name, d.result)
                _new_object(Portal(name))
                self.obj.guess_link()

            def import_object():
                fname = tkfiledialog.askdirectory(
                    initialdir="./data/scenes/mship",
                    title='Please select a directory containing an Actor, Item or Scene')

                name = os.path.basename(fname)
                for obj_cls in [Actor, Item, Emitter, Portal, Scene]:
                    dname = "directory_%ss" % obj_cls.__name__.lower()
                    if getattr(self.game, dname) in fname:  # guess the class
                        o = obj_cls(name)
                        self.game.immediate_add(o)
                        o.smart(self.game)
                        refresh(self._sceneselect)
                        tkmessagebox.showwarning(
                            "Import Object",
                            "Imported %s as new %s" % (
                                name, obj_cls.__name__.lower()),
                        )
                        return
                tkmessagebox.showwarning(
                    "Import Object",
                    "Cannot guess the type of object (is it stored in data/actors data/items data/scenes?)"
                )

            self.add_object = tk.Button(
                group, text='Add Object', command=add_object).grid(column=2, row=row)

            self.new_actor = tk.Button(
                group, text='New Actor', command=new_actor).grid(column=3, row=row)
            self.new_item = tk.Button(
                group, text='New Item', command=new_item).grid(column=4, row=row)
            self.new_portal = tk.Button(
                group, text='New Portal', command=new_portal).grid(column=5, row=row)
            self.import_object = tk.Button(
                group, text='Import Object', command=import_object).grid(column=6, row=row)

            menu_item = tk.StringVar(group)

            def edit_menu_item(*args, **kwargs):
                mitem = get_object(self.game, menu_item.get())
                edit_object_script(self.game, mitem)

            row += 1
            tk.Label(group, text="Edit menu item:").grid(column=1, row=row)
            menu = [x for x in self.game.menu_items]
            menu.sort()
            if len(menu) > 0:
                tk.OptionMenu(group, menu_item, *menu, command=edit_menu_item).grid(column=2, row=row)

            row += 1

            def edit_camera():
                self.game.editing = self.game.scene
                self.game._editing_point_set = (
                    self.game.get_scene().set_x, self.game.get_scene().set_y)
                self.game._editing_point_get = (
                    self.game.get_scene().get_x, self.game.get_scene().get_y)

            tk.Radiobutton(group, text="Camera", command=edit_camera,
                           indicatoron=0, value=1).grid(row=row, column=0)

            request_default_idle = tk.StringVar(group)

            def change_default_idle(*args, **kwargs):
                self.game.get_scene().default_idle = request_default_idle.get()

            col = 1
            if self.game.player:
                actions = list(self.game.get_player().actions.keys())
            else:
                actions = []
            actions.sort()
            if len(actions) > 0:
                tk.Label(group, text="Default player idle for scene:").grid(
                    column=col, row=row)
                tk.OptionMenu(
                    group, request_default_idle, *actions, command=change_default_idle).grid(column=col + 1, row=row)
                # row += 1
                col += 2

            def close_editor(*args, **kwargs):
                if self.obj:
                    self.obj.show_debug = False
                if self.game.editing:
                    obj = get_object(self.game, self.game.editing)
                    obj.show_debug = False
                    self.game.editing = None  # switch off editor
                self.game.editor = None
                self.app.destroy()

            self.close_button = tk.Button(
                group, text='close', command=close_editor).grid(column=col, row=row)

            row += 1

            def save_state(*args, **kwargs):
                for i in glob.glob("%s/*" % self.game.get_scene().directory):
                    print("f", i)
                s = input('state name (eg tmp.py)>')
                if s == "":
                    return
                else:
                    state_name = os.path.splitext(os.path.basename(s))[0]
                    print("save %s to %s" % (state_name, self.game.get_scene().directory))
                    self.game._save_state(state_name)
                return
                # non-threadsafe
                d = tkfiledialog.SaveFileDialog(self.app)
                pattern, default, key = "*.py", "", None
                fname = d.go(self.game.get_scene().directory, pattern, default, key)
                if fname is None:
                    return
                else:
                    state_name = os.path.splitext(os.path.basename(fname))[0]
                    self.game._save_state(state_name)

            def load_state(*args, **kwargs):
                d = tkfiledialog.LoadFileDialog(self.app)
                pattern, default, key = "*.py", "", None
                fname = d.go(self.game.get_scene().directory, pattern, default, key)
                if fname is None:
                    return
                else:
                    state_name = os.path.splitext(os.path.basename(fname))[0]
                    self.game.load_state(self.game.scene, state_name)
                    self.game.get_scene().add(self.game.player)

            def initial_state(*args, **kwargs):
                if self.game.player:
                    player_in_scene = self.game.get_player().name in self.game.get_scene().objects
                else:
                    player_in_scene = None
                self.game.load_state(self.game.scene, "initial")
                if player_in_scene: self.game.get_scene().add(self.game.player)

            def save_layers(*args, **kwargs):
                self.game.get_scene()._save_layers()

            def edit_interact_scripts(*args, **kwargs):
                for i in self.game.get_scene().objects:
                    obj = get_object(self.game, i)
                    if obj.allow_interact or obj.allow_look:
                        edit_object_script(self.game, obj)

            def edit_flip_scene(*args, **kwargs):
                w = self.game.resolution[0]
                for i in self.game.get_scene().objects:
                    obj = get_object(self.game, i)
                    if obj == self.game.player:
                        continue
                    obj.x = w - obj.x
                    obj._sx = - obj._sx
                    obj._ax = - obj._ax
                    obj._tx = - obj._tx
                    obj._nx = - obj._nx
                self.game.get_scene().walkarea.mirror(w)

            def _edit_walkarea(scene):
                scene.walkarea.immediate_toggle_editor()
                if scene.walkarea.editing:
                    self.game.editing = scene.walkarea
                    self.game._editing_point_set = (
                        scene.walkarea.set_pt_x, scene.walkarea.set_pt_y)
                    self.game._editing_point_get = (
                        scene.walkarea.get_pt_x, scene.walkarea.get_pt_y)
                    scene.walkarea._edit_polygon_index = 1

            def reset_walkarea(*args, **kwargs):
                self.game.get_scene().walkarea.reset_to_default()

            def edit_walkarea(*args, **kwargs):
                _edit_walkarea(self.game.scene)

            self.state_save_button = tk.Button(
                group, text='save state', command=save_state).grid(column=0, row=row)
            self.state_load_button = tk.Button(
                group, text='load state', command=load_state).grid(column=1, row=row)
            self.state_initial_button = tk.Button(
                group, text='initial state', command=initial_state).grid(column=2, row=row)
            self.layer_save_button = tk.Button(
                group, text='save layers', command=save_layers).grid(column=3, row=row)
            self.layer_save_button = tk.Button(
                group, text='Edit scripts', command=edit_interact_scripts).grid(column=4, row=row)
            self.layer_save_button = tk.Button(
                group, text='Flip scene', command=edit_flip_scene).grid(column=5, row=row)

            row += 1

            def add_edge_point(*args, **kwargs):
                if self.game.get_scene().walkarea:
                    self.game.get_scene().walkarea.insert_edge_point()

            def add_way_point(*args, **kwargs):
                if self.game.get_scene().walkarea:
                    self.game.get_scene().walkarea.insert_way_point()

            self.reset_walkarea_button = tk.Button(
                group, text='reset walkarea', command=reset_walkarea).grid(column=1, row=row)
            self.edit_walkarea_button = tk.Button(
                group, text='edit walkarea', command=edit_walkarea).grid(column=2, row=row)

            self.edit_walkarea_button = tk.Button(
                group, text='add edge point', command=add_edge_point).grid(column=3, row=row)

            self.edit_walkarea_button = tk.Button(
                group, text='add way point', command=add_way_point).grid(column=4, row=row)

            row += 1

            def _navigate(delta):
                objects = self.game.get_scene().objects + self.game.get_scene().layers
                num_objects = len(objects)
                if num_objects == 0:
                    print("No objects in scene")
                    return
                obj = objects[self.index]
                obj = get_object(self.game, obj)
                obj.show_debug = False
                self.index += delta
                if self.index < 0:
                    self.index = num_objects - 1
                if self.index >= num_objects:
                    self.index = 0
                obj = objects[self.index]
                self.set_edit_object(obj)

            def prev():
                _navigate(-1)  # decrement navigation

            def next():
                _navigate(1)  # increment navigation

            def selector():
                """ The next click on the game window will select an object
                in the editor.
                :return:
                """
                self.game._selector = True

            self.prev_button = tk.Button(
                group, text='<-', command=prev).grid(column=0, row=row)
            #        self.edit_button = tk.Button(group, text='Edit', command=self.create_editor)
            #        self.edit_button.grid(column=1, row=row)
            self.next_button = tk.Button(
                group, text='->', command=next).grid(column=2, row=row)
            self.selector_button = tk.Button(
                group, text='selector', command=selector).grid(column=3, row=row)

            self.rows = row

        def create_editor_widgets(self):
            obj = get_object(self.game, self.obj)
            if not obj:
                print("editor widgets can't find", self.obj)
                return
            self.obj = obj
            row = 0
            self.editor_label = group = tk.LabelFrame(
                self.app, text=obj.name, padx=5, pady=5)
            group.grid(padx=10, pady=10)

            self.editing = tk.StringVar(self.app)
            self.editing.set("Nothing")

            self._editing_bool = {}

            frame = group
            row = self.rows

            def selected():
                for editable in self.obj._editable:
                    # this is what we want to edit now.
                    if self.editing.get() == editable[0]:
                        label, get_attrs, set_attrs, types = editable
                        self.game.editing = self.obj
                        self.game._editing_point_set = set_attrs
                        self.game._editing_point_get = get_attrs
                        self.game._editing_label = label

            def edit_btn():
                """ Open the script for this object for editing """
                obj = self.obj
                edit_object_script(self.game, obj)

            def reset_btn():
                """ Reset the main editable variables for this object """
                obj = self.obj
                obj.x, obj.y = self.game.resolution[
                                   0] / 2, self.game.resolution[1] / 2
                obj.ax, obj.ay = 0, 0
                w = obj.w if obj.w else 0
                obj.sx, obj.sy = w, 0
                obj.nx, obj.ny = w, -obj.h

            def toggle_bools(*args, **kwargs):
                """ Updates all bools that are being tracked """
                for editing, v in self._editing_bool.items():
                    for editable in self.obj._editable:
                        # this is what we want to edit now.
                        if editing == editable[0]:
                            label, get_attr, set_attr, types = editable
                            v = True if v.get() == 1 else False
                            set_attr(v)

            #            editing = self._editing_bool.get()[:-2]
            #            val = True if self._editing_bool.get()[-1:] == "t" else False
            #            print("Set %s to %s"%(editing, val))
            #                    self.game.editing = self.obj
            #                    self.game._editing_point_set = set_attrs
            #                    self.game._editing_point_get = get_attrs

            for i, editable in enumerate(obj._editable):
                label, get_attrs, set_attrs, types = editable
                btn = tk.Radiobutton(
                    frame, text=label, variable=self.editing, value=label, indicatoron=0, command=selected)
                btn.grid(row=row, column=0)
                if type(types) == tuple:  # assume two ints
                    e1 = tk.Entry(frame)
                    e1.grid(row=row, column=1)
                    e1.insert(0, int(get_attrs[0]()))
                    e2 = tk.Entry(frame)
                    e2.grid(row=row, column=2)
                    e2.insert(0, int(get_attrs[1]()))
                    obj._tk_edit[label] = (e1, e2)
                elif types == str:
                    e = tk.Entry(frame)
                    e.grid(row=row, column=1, columnspan=2)
                    obj._tk_edit[label] = e
                #                if get_attrs: e.insert(0, get_attrs())
                elif types == bool:
                    # value="%s%s"%(label, val)
                    self._editing_bool[label] = tk.IntVar(self.app)
                    self._editing_bool[label].set(get_attrs())
                    tk.Checkbutton(frame, variable=self._editing_bool[
                        label], command=toggle_bools, onvalue=True, offvalue=False).grid(row=row, column=1,
                                                                                         columnspan=2)
                elif types == float:
                    e = tk.Entry(frame)
                    e.grid(row=row, column=1)
                    e.insert(0, int(get_attrs()))
                    obj._tk_edit[label] = e

                row += 1

            action = tk.StringVar(group)

            def change_action(*args, **kwargs):
                self.obj.do(action.get())

            def edit_motion_btn(*args, **kwargs):
                action_to_edit = self.obj.actions[
                    action.get()] if action.get() in self.obj.actions else None
                if action_to_edit:
                    edit_action_motion(self.game, self.obj, action_to_edit)

            # XXX editor can only apply one motion at a time, should probably use a
            # checkbox list or something
            def apply_motion_btn(*args, **kwargs):
                self.obj.motion(action.get())

            actions = [x.name for x in obj.actions.values()]
            actions.sort()
            if len(actions) > 0:
                tk.Label(group, text="Action:").grid(column=0, row=row)
                tk.OptionMenu(
                    group, action, *actions, command=change_action).grid(column=1, row=row)
                self.edit_motion_btn = tk.Button(
                    frame, text="Edit Motion", command=edit_motion_btn).grid(row=row, column=2)
                self.apply_motion_btn = tk.Button(
                    frame, text="Apply Motion", command=apply_motion_btn).grid(row=row, column=3)
                row += 1

            request_idle = tk.StringVar(group)

            def change_idle(*args, **kwargs):
                self.obj.idle_stand = request_idle.get()

            if self.game.player:
                actions = [x.name for x in self.game.get_player().actions.values()]
                actions.sort()
            else:
                actions = []
            if len(actions) > 0:
                tk.Label(group, text="Requested player action on stand:").grid(
                    column=0, row=row)
                tk.OptionMenu(
                    group, request_idle, *actions, command=change_idle).grid(column=1, row=row)
                row += 1

            group = tk.LabelFrame(group, text="Tools", padx=5, pady=5)
            group.grid(padx=10, pady=10)

            self.edit_script = tk.Button(
                frame, text="Edit Script", command=edit_btn).grid(row=row, column=0)

            def remove_btn():
                self.obj.show_debug = False
                self.game.get_scene().remove(self.obj)
                objects = self.game.get_scene().objects
                if len(objects) > 0:
                    self.obj = get_object(self.game, objects[0])

            def refresh_btn():
                """ Reload object """
                obj = self.obj
                obj.smart(self.game)
                self.game.immediate_add(obj, replace=True)

            self.remove_btn = tk.Button(
                frame, text="Remove", command=remove_btn).grid(row=row, column=1)
            self.refresh_btn = tk.Button(
                frame, text="Reload", command=refresh_btn).grid(row=row, column=3)
            self.reset_btn = tk.Button(
                frame, text="Reset", command=reset_btn).grid(row=row, column=4)

            row += 1
            self.rows = row

        def create_widgets(self):
            """
            Top level game navigator: scene select, add actor, remove actor, cycle actors, save|load state
            """
            #        group = self.app

            # frame = self  # self for new window, parent for one window
            self.create_navigator_widgets()
            self.create_editor_widgets()

        def run(self):
            self.app = tk.Tk()
            #        self.app.wm_attributes("-topmost", 1)
            self.create_widgets()
            self.app.mainloop()


def editor(game):  # pragma: no cover
    """ Create the editor app """
    if not EDITOR_AVAILABLE:
        return None
    app = MyTkApp(game)
    return app
