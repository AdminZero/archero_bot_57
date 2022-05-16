import json
import time
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal
from UsbConnector import UsbConnector
from GameScreenConnector import GameScreenConnector
from StatisticsManager import StatisticsManager
from Utils import loadJsonData, saveJsonData_oneIndent, saveJsonData_twoIndent, readAllSizesFolders, buildDataFolder, getCoordFilePath
import enum
import os

class HealingStrategy(str, enum.Enum):
    AlwaysHeal = "always_heal"
    AlwaysPowerUp = "always_power"

class CaveEngine(QObject):
    levelChanged = pyqtSignal(int)
    addLog = pyqtSignal(str)
    resolutionChanged = pyqtSignal(int, int)
    dataFolderChanged = pyqtSignal(str)
    noEnergyLeft = pyqtSignal()
    gameWon = pyqtSignal()
    gamePaused = pyqtSignal()
    healingStrategyChanged = pyqtSignal(HealingStrategy)
    currentDungeonChanged = pyqtSignal(int)
    
    max_level = 20 # set loops for playCave and linked to GUI logs(default is 20, DO NOT CHANGE)
    playtime = 100 # set loops for letPlay (default 100, total patrol loops = playtime/self.check_seconds)
    max_loops_popup = 10 # set loops for reactGamePopups (default 10, times to check for popups)
    max_loops_game = 25 # set loops for start_one_game (default 20, farming cycles to do)
    max_wait = 10 # set loops for final_boss (default 10, increase sleep screens if need more time)
    sleep_btw_screens = 5 # set wait between loops for final_boss (default 5, in seconds)
    
    UseGeneratedData = False # Set True to use TouchManager generated data
    SkipEnergyCheck = False # Set True to not check for energy (not recommended)
    
    data_pack = 'datas'
    coords_path = 'coords'
    buttons_filename = "buttons.json"
    movements_filename = "movements.json"
    print_names_movements = {
        "n": "up",
        "s": "down",
        "e": "right",
        "w": "left",
        "ne": "up-right",
        "nw": "up-left",
        "se": "down-right",
        "sw": "down-left",
    }

    allowed_chapters = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

    chapters = {
        "1": "Verdant Prairie",
        "2": "Storm Desert",
        "3": "Abandoned Dungeon",
        "4": "Crystal Mines",
        "5": "Lost Castle",
        "6": "Cave of Bones",
        "7": "Barens of Shadow",
        "8": "Silent Expanse",
        "9": "Frozen Pinnacle",
        "10": "Land of Doom",
        "11": "The Capital",
        "12": "Dungeon of Traps",
        "13": "Lava Land",
        "14": "Eskimo Lands",
        "15": "Pharaoh's Chamber",
        "16": "Archaic Temple",
        "17": "Dragon Lair",
        "18": "Escape Chamber",
        "19": "devil's Tavern",
        "20": "Palace of Light",
        "21": "Nightmare Land",
        "22": "Tranquil Forest",
        "23": "Underwater Ruins",
        "24": "Silent Wilderness",
        "25": "Death Bar",
        "26": "Land of the Dead",
        "27": "Sky Castle",
        "28": "Sandy Town",
        "29": "dark forest",
        "30": "Shattered Abyss",
        "31": "Underwater City",
        "32": "Evil Castle",
        "33": "Aeon Temple",
        "34": "sakura Court"
    }

    t_intro = 'intro'
    t_normal = 'normal'
    t_heal = 'heal'
    t_boss = 'boss'
    t_final_boss = 'final_boss'

    levels_type = {
        0: t_intro,
        1: t_normal,
        2: t_heal,
        3: t_normal,
        4: t_heal,
        5: t_boss,
        6: t_normal,
        7: t_heal,
        8: t_normal,
        9: t_heal,
        10: t_boss,
        11: t_normal,
        12: t_heal,
        13: t_normal,
        14: t_heal,
        15: t_boss,
        16: t_normal,
        17: t_heal,
        18: t_normal,
        19: t_heal,
        20: t_final_boss,
    }

    def __init__(self, connectImmediately: bool = False):
        super(QObject, self).__init__()
        self.debug = True # set False to stop print debug messages in console
        self.vip_priv_rewards = True # set True if you get VIP or Privledge rewards
        self.currentLevel = 0
        self.currentDungeon = 6 
        self.check_seconds = 5
        self.load_tier_list()
        self.statisctics_manager = StatisticsManager()
        self.start_date = datetime.now()
        self.stat_lvl_start = 0
        self.screen_connector = GameScreenConnector()
        self.screen_connector.debug = False
        self.width, self.heigth = 1080, 1920 
        self.device_connector = UsbConnector()
        self.device_connector.setFunctionToCallOnConnectionStateChanged(self.onConnectionStateChanged)
        self.buttons = {}
        self.movements = {}
        self.disableLogs = False
        self.stopRequested = False
        self.currentDataFolder = ''
        self.dataFolders = {}
        self.healingStrategy = HealingStrategy.AlwaysPowerUp
        self.current_settings = {}
        self.current_settings_path = 'current_settings.json'
        self.load_current_settings()
        self.centerAfterCrossingDungeon = False
        if connectImmediately:
            self.initDeviceConnector()

    def load_tier_list(self):
        if self.debug: print("Loading Abilities Tier List")
        file = os.path.join("datas", "abilities", "tier_list.json")
        with open(file) as file_in:
            self.tier_list_abilities = json.load(file_in)

    def initDataFolders(self):
        if self.debug: print("Initalizing Data Folders")
        self.dataFolders = readAllSizesFolders()
        deviceFolder = buildDataFolder(self.width, self.heigth)
        first_folder = list(self.dataFolders.keys())[0]
        if deviceFolder not in self.dataFolders:
            if self.debug: print("Error: not having %s coordinates. Trying with %s" % (deviceFolder, first_folder))
            deviceFolder = first_folder
        self.changeCurrentDataFolder(deviceFolder)

    def initdeviceconnector(self):
        if self.debug: print("Initalizing Device Connector")
        self.device_connector.connect()

    def _create_default_current_settings(self):
        if self.debug: print("Loading Default Settings")
        new_sett = {
            "healing_strategy": HealingStrategy.AlwaysHeal,
            "selected_dungeon": 6
        }
        saveJsonData_oneIndent(self.current_settings_path, new_sett)

    def load_current_settings(self):
        if self.debug: print("Loading Current Settings")
        if not os.path.exists(self.current_settings_path):
            if self.debug: print("Creating basic current settings...")
            self._create_default_current_settings()
        try:
            new_sett = loadJsonData(self.current_settings_path)
        except Exception as e:
            if self.debug: print("Unable to load existing {}: {}. setting to default.".format(self.current_settings_path, str(e)))
            self._create_default_current_settings()
            new_sett = loadJsonData(self.current_settings_path)
        if "healing_strategy" not in new_sett or "selected_dungeon" not in new_sett:
            if self.debug: print("Corrupted/errored current settings. ")
            if self.debug: print("Creating basic current settings...")
            self._create_default_current_settings()
        new_sett = loadJsonData(self.current_settings_path)
        self.current_settings = new_sett
        self.healingStrategy = HealingStrategy(self.current_settings["healing_strategy"])
        self.currentDungeon = int(self.current_settings["selected_dungeon"])

    def changeHealStrategy(self, strat: HealingStrategy):
        if self.debug: print("Loading Heal Strategy")
        self.healingStrategy = strat
        self.current_settings['healing_strategy'] = self.healingStrategy
        saveJsonData_oneIndent(self.current_settings_path, self.current_settings)
        self.healingStrategyChanged.emit(strat)

    def changeChapter(self, new_chapter):
        if self.debug: print("Loading Selected Chapter")
        self.currentDungeon = new_chapter
        self.current_settings['selected_dungeon'] = str(self.currentDungeon)
        saveJsonData_oneIndent(self.current_settings_path, self.current_settings)
        self.currentDungeonChanged.emit(new_chapter)

    def onConnectionStateChanged(self, connected):
        if self.debug: print("Detecting Connection State")
        if connected:
            if self.debug: print("Device Detected")
            self.initDataFolders()
            self.screen_connector.changeDeviceConnector(self.device_connector)
            self.updateScreenSizeByPhone()
        else:
            if self.debug: print("No Device Detected")

    def updateScreenSizeByPhone(self):
        if self.device_connector is not None:
            w, h = self.device_connector.adb_get_size()
            self.changeScreenSize(w, h)
            self.screen_connector.changeScreenSize(w, h)
        else:
            if self.debug: print("Device connector is none. initialize it before calling this method!")

    def changeCurrentDataFolder(self, new_folder):
        self.currentDataFolder = new_folder
        self.loadCoords()
        self.dataFolderChanged.emit(new_folder)

    def loadCoords(self):
        if self.debug: print("Loading Coordinates")
        self.buttons = loadJsonData(getCoordFilePath(self.buttons_filename, sizePath = self.currentDataFolder))
        self.movements = loadJsonData(getCoordFilePath(self.movements_filename, sizePath = self.currentDataFolder))

    def setStopRequested(self):
        if self.debug: print("Stop Requested")
        self.stopRequested = True
        self.screen_connector.stopRequested = True
        if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
            if self.debug: print("*** Saving Statistics #3 ***")
            self.statisctics_manager.saveOneGame(self.start_date, self.stat_lvl_start, self.currentLevel)

    def setStartRequested(self):
        if self.debug: print("Start Requested")
        self.stopRequested = False
        self.screen_connector.stopRequested = False
        self.gamePaused.emit()

    def changeScreenSize(self, w, h):
        self.width, self.heigth = w, h
        if self.debug: print("New resolution set: %dx%d" % (self.width, self.heigth))
        self.resolutionChanged.emit(w, h)
        
    def __unused__initConnection(self):
        device = self.device_connector._get_device_id()
        if device is None:
            if self.debug: print("Error: no device discovered. Start adb server before executing this.")
            exit(1)
        if self.debug: print("Usb debugging device: %s" % device)

    def log(self, log: str):
        """
        Logs an important move in the bot game
        """
        if not self.disableLogs:
            self.addLog.emit(log)

    def swipe_points(self, start, stop, s):
        start = self.buttons[start]
        stop = self.buttons[stop]
        if self.debug: print("Swiping between %s and %s in %f" % (start, stop, s))
        self.device_connector.adb_swipe(
            [start[0] * self.width, start[1] * self.heigth, stop[2] * self.width, stop[3] * self.heigth], s)

    def swipe(self, name, s):
        if self.stopRequested:
            exit()
        coord = self.movements[name]
        if self.debug: print("Swiping %s in %f" % (self.print_names_movements[name], s))
        self.log("Swipe %s in %.2f" % (self.print_names_movements[name], s))
        # convert back from normalized values
        self.device_connector.adb_swipe(
            [coord[0][0] * self.width, coord[0][1] * self.heigth, coord[1][0] * self.width, coord[1][1] * self.heigth],
            s)

    def tap(self, name):
        if self.stopRequested:
            exit()
        self.log("Tap %s" % name)
        # convert back from normalized values
        x, y = int(self.buttons[name][0] * self.width), int(self.buttons[name][1] * self.heigth)
        if self.debug: print("Tapping on %s at [%d, %d]" % (name, x, y))
        self.device_connector.adb_tap((x, y))

    def wait(self, s):
        decimal = s
        if int(s) > 0:
            decimal = s - int(s)
            for _ in range(int(s)):
                if self.stopRequested:
                    exit()
                time.sleep(1)
        if self.stopRequested:
            exit()
        time.sleep(decimal)

    def changeCurrentLevel(self, new_lvl):
        self.currentLevel = new_lvl
        self.levelChanged.emit(self.currentLevel)

    def quick_test_functions(self):
        pass

    def start_infinite_play(self):
        while True:
            self.start_one_game()
            self.currentLevel = 0

    def exit_dungeon_uncentered(self):
        if self.debug: print("exit_dungeon_uncentered")
        self.reactGamePopups()
        self.log("No Loot Left")
        self.log("Leaveing Dungeon")
        if self.currentDungeon == 3:
            self.exit_movement_dungeon6()
        elif self.currentDungeon == 6:
            self.exit_movement_dungeon6()
        elif self.currentDungeon == 10:
            self.exit_movement_dungeon10()
        else:
            self.exit_movement_dungeon_old()
        self.exit_dungeon_uncentered_simplified()

    def exit_dungeon_uncentered_simplified(self, do_second_check = True):
        if do_second_check:
            if self.debug: print("exit_dungeon_uncentered_simplified_check")
            if self.screen_connector.getFrameState() != "in_game":
                self.reactGamePopups()
                self.exit_dungeon_uncentered_simplified(do_second_check = False)
                if self.currentDungeon == 3:
                    self.exit_movement_dungeon6()
                elif self.currentDungeon == 6:
                    self.exit_movement_dungeon6()
                elif self.currentDungeon == 10:
                    self.exit_movement_dungeon10()
                else:
                    self.exit_movement_dungeon_old()
        if self.debug: print("exit_dungeon_uncentered_simplified")
        self.log("Left Dungeon")
        self.wait(1) # wait to load to GUI

    def exit_movement_dungeon_old(self):
        if self.debug: print("exit_dungeon_old 'Improved'")
        self.disableLogs = True
        self.swipe('ne', 3)
        self.swipe('nw', 3)
        self.swipe('ne', 2)
        self.swipe('nw', 1)
        self.disableLogs = False

    def exit_movement_dungeon6(self):
        if self.debug: print("exit_dungeon_6")
        self.disableLogs = True
        self.swipe('w', 2)
        self.swipe('ne', 3)
        self.disableLogs = False

    def exit_movement_dungeon10(self):
        if self.debug: print("exit_dungeon_10")
        self.disableLogs = True
        self.swipe('e', 2)
        self.swipe('nw', 3)
        self.disableLogs = False
   
    def goTroughDungeon10(self):
        if self.debug: print("Going through dungeon (designed for #10)")
        self.log("Crossing Dungeon 10")
        self.disableLogs = True
        self.swipe('n', .5)
        self.swipe('nw', 2.5)
        self.wait(2)
        self.swipe('ne', 2.5)
        self.wait(2)
        self.swipe('nw', 2)
        self.wait(1)
        self.swipe('s', .6)
        self.swipe('e', .4)
        self.swipe('ne', .4)
        self.swipe('n', 3)
        self.wait(1)
        self.swipe('s', .3)
        self.swipe('w', .3)
        self.swipe('nw', .3)
        self.swipe('n', 1)
        if self.currentLevel == 18:
            if self.debug: print("Adjusting lvl 18 Position")
            self.disableLogs = False
            self.log("Level 18 Argh!")
            self.disableLogs = True
            self.swipe('w', .3)
            self.swipe('s', .3)
            self.swipe('ne', .3)
            self.swipe('nw', 2)
        self.disableLogs = False

    def goTroughDungeon6(self):
        if self.debug: print("Going through dungeon (designed for #6)")
        self.log("Crossing Dungeon 6")
        self.disableLogs = True
        self.swipe('n', 1.5)
        self.swipe('w', .3)
        self.swipe('n', .6)
        self.wait(2)
        self.swipe('e', .6)
        self.swipe('n', .6)
        self.wait(2)
        self.swipe('w', .6)
        self.swipe('n', 1.5)
        self.wait(2)
        self.swipe('e', .3)
        self.swipe('n', 2)
        self.disableLogs = False

    def goTroughDungeon3(self):
        if self.debug: print("Going through dungeon (designed for #3)")
        self.log("Crossing Dungeon 3")
        self.disableLogs = True
        self.swipe('n', 1.5)
        self.swipe('w', .25)
        self.swipe('n', .5)
        self.wait(1)
        self.swipe('e', .25)
        self.swipe('n', 2)
        self.wait(1)
        self.swipe('w', 1)
        self.swipe('n', .5)
        self.swipe('e', 1)
        self.swipe('n', 1.5)
        self.disableLogs = False

    def goTroughDungeon_old(self):
        if self.debug: print("Going through dungeon old 'Improved'")
        self.log("Crossing Dungeon (Improved)")
        self.disableLogs = True
        self.swipe('n', .6)
        self.swipe('nw', 2)
        self.wait(1)
        self.swipe('s', .6)
        self.swipe('e', 1)
        self.swipe('nw', 2)
        self.wait(1)
        self.swipe('s', .6)
        self.swipe('w', 1)
        self.swipe('ne', 2)
        self.wait(1)
        self.swipe('s', .4)
        self.swipe('e', .3)
        self.swipe('ne', 1)
        self.wait(1)
        self.swipe('s', .4)
        self.swipe('w', .3)
        self.swipe('nw', 1.5)
        self.swipe('ne', 2.5)
        self.disableLogs = False

    def goTroughDungeon(self):
        if self.currentDungeon == 3:
            self.goTroughDungeon3()
        elif self.currentDungeon == 6:
            self.goTroughDungeon6()
        elif self.currentDungeon == 10:
            self.goTroughDungeon10()
        else:
            self.goTroughDungeon_old()
        if self.centerAfterCrossingDungeon: self.centerPlayer() # set True-False in '__init__'

    def centerPlayer(self): # still not working correctly always 540px to left.
        px, dir = self.screen_connector.getPlayerDecentering()
        duration = 0.019 * abs(px) - 4.8
        if px < self.screen_connector.door_width / 2.0:
            pass
        if dir == 'left':
            self.log("Centered Player <--")
            self.swipe('e', duration)
        elif dir == 'right':
            self.log("Centered Player -->")
            self.swipe('w', duration)
        elif dir == "center":
            pass

    def letPlay(self, _time: int, is_boss = False):
        check_exp_bar = not is_boss
        experience_bar_line = self.screen_connector.getLineExpBar()
        frame = self.screen_connector.getFrame()
        state = self.screen_connector.getFrameState(frame)
        recheck = False
        if self.debug: print("Let-Play. Auto playing...")
        self.log("Searching the dungeon")
        for i in range(_time, 0, -1):
            if i % self.check_seconds == 0 or recheck:
                experience_bar_line = self.screen_connector.getLineExpBar()
                frame = self.screen_connector.getFrame()
                state = self.screen_connector.getFrameState(frame)
                recheck = False
                print("Loop Countdown / Kill Timer")
                print(i)
                if self.debug: print("Let Play. Checking screen...")
                if self.debug: print("state: %s" % state)
                if state == "unknown":
                    if self.debug: print("Unknown screen situation detected. Checking again...")
                    if self.screen_connector.getFrameState() == "unknown":
                        self.wait(5) # wait before double check
                        if self.debug: print("Unknown screen situation detected. Checking again x2...")
                        if self.screen_connector.getFrameState() == "unknown":
                            raise Exception('unknown_screen_state')
                        else:
                            recheck = True
                            continue
                    else:
                        recheck = True
                        continue
                elif state == "endgame" or state == "repeat_endgame_question":
                    if self.debug: print("Ley-Play. Endgame Detected")
                    if state == "repeat_endgame_question":
                        if self.debug: print("state = repeat_endgame_question")
                    if self.debug: print("You died or you won! Either way, game over!")
                    self.log("You died or won!")
                    self.log("Either way, it's over!")
                    self.pressCloseEndgame()
                    return
                elif state == "menu_home":
                    raise Exception('mainscreen')
                elif state == "select_ability":
                    if self.debug: print("Level ended. New Abilities.")
                    self.log("New Abilities")
                    return
                elif state == "fortune_wheel" :
                    if self.debug: print("Level ended. Fortune Wheel.")
                    self.log("Fortune Wheel")
                    return
                elif state == "devil_question":
                    if self.debug: print("Level ended. Devil Arrived.")
                    self.log("Devil Arrived")
                    return
                elif state == "mistery_vendor":
                    if self.debug: print("Level ended. Mystery Vendor.")
                    self.log("Mystery Vendor")
                    return
                elif state == "ad_ask":
                    if self.debug: print("Level ended. Ad Ask.")
                    self.log("Ad Ask")
                    return
                elif state == "angel_heal":
                    if self.debug: print("Level ended. Angel Appeared.")
                    self.log("Angel Arrived")
                    return
                elif check_exp_bar and self.screen_connector.checkExpBarHasChanged(experience_bar_line, frame):
                    if self.debug: print("Experience gained!")
                    self.log("Gained Experience")
                    return
                elif state == "in_game":
                    # added movement to increase kill enemy efficency
                    if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
                        if self.screen_connector.checkDoorsOpen(frame):
                            if self.debug: print("Door is OPEN #1 <---------######")
                            self.log("The Door is Open")
                            return
                        if self.screen_connector.checkDoorsOpen1(frame):
                            if self.debug: print("Door is OPEN #2 <---------######")
                            self.log("The Door is Open")
                            return
                        if self.screen_connector.checkDoorsOpen2(frame):
                            if self.debug: print("Door is OPEN #3 <---------######")
                            self.log("The Door is Open")
                            return
                        else:
                            if self.debug: print("Doing patrol")
                            self.log("Doing Patrol")
                            self.disableLogs = True
                            self.swipe('w', 0.66)
                            self.wait(2)
                            self.swipe('e', 0.33)
                            self.wait(2)
                            self.swipe('e', 0.66)
                            self.wait(2)
                            self.swipe('w', 0.33)
                            self.disableLogs = False
                            if self.debug: print("Still playing but level not ended")
                    # added random escape methods for 10, 30, 50 level chapters
                    else:
                        if i >= _time * .85:
                                if self.debug: print("Let-Play. Time < 100%")
                                self.log("Escape route #1")
                                self.disableLogs = True
                                self.swipe('s', 0.6)
                                self.swipe('w', 0.4)
                                self.swipe('nw', 2)
                                self.swipe('ne', 3)
                                self.swipe('s', 0.6)
                                self.swipe('e', 0.4)
                                self.swipe('ne', 2)
                                self.swipe('nw', 3)
                                self.disableLogs = False
                        if _time * .7 <= i < _time * .85:
                                if self.debug: print("Let-Play. Time < 85%")
                                self.log("Escape route #2")
                                self.disableLogs = True
                                self.swipe('s', .5)
                                self.swipe('sw', 2)
                                self.swipe('n', 1)
                                self.swipe('nw', 2)
                                self.swipe('ne', 2)
                                self.swipe('s', .5)
                                self.swipe('se', 2)
                                self.swipe('n', 1)
                                self.swipe('ne', 2)
                                self.swipe('nw', 2)
                                self.disableLogs = False
                        if _time * .5 <= i < _time * .7:
                                if self.debug: print("Let-Play. Time < 70%")
                                self.log("Escape route #3")
                                self.disableLogs = True
                                self.swipe('s', .3)
                                self.swipe('ne', 1)
                                self.swipe('nw', 2)
                                self.swipe('s', .3)
                                self.swipe('nw', 1)
                                self.swipe('ne', 2)
                                self.disableLogs = False
                        if _time * .35 <= i < _time * .5:
                                if self.debug: print("Let-Play. Time < 50%")
                                self.log("Escape route #4")
                                self.disableLogs = True
                                self.swipe('sw', 2)
                                self.swipe('n', 1)
                                self.swipe('ne', 2)
                                self.swipe('se', 2)
                                self.swipe('w', 1)
                                self.swipe('nw', 2)
                                self.swipe('ne', 2)
                                self.disableLogs = False
                        if i < _time * .35:
                                if self.debug: print("Let-Play. Time < 35%")
                                self.log("Escape route #4")
                                self.disableLogs = True
                                self.swipe('se', 2)
                                self.swipe('n', 1)
                                self.swipe('nw', 2)
                                self.swipe('sw', 2)
                                self.swipe('n', 2)
                                self.swipe('ne', 2)
                                self.swipe('nw', 2)
                                self.disableLogs = False
                        else:
                            if self.debug: print("Still playing but level not ended")

    def reactGamePopups(self) -> int:
        state = ""
        i = 0
        while state != "in_game":
            if self.stopRequested:
                exit()
            if i > self.max_loops_popup:
                if self.debug: print("React-Popups. Max loops reached")
                raise Exception('unknown_screen_state')    
            if self.debug: print("React-Popups. Checking screen...")
            state = self.screen_connector.getFrameState()
            if self.debug: print("state: %s" % state)
            if state == "select_ability":
                self.chooseBestAbility()
            elif state == "fortune_wheel":
                self.tap('lucky_wheel_start')
                self.wait(6)
            elif state == "devil_question":
                self.tap('ability_daemon_reject')
                self.wait(2)
            elif state == "ad_ask":
                self.tap('spin_wheel_back')
                self.wait(2)
            elif state == "mistery_vendor":
                self.tap('spin_wheel_back')
                self.wait(2)
            elif state == "special_gift_respin":
                self.tap('spin_wheel_back')
                self.wait(2)
            elif state == "angel_heal":
                self.tap('heal_right' if self.healingStrategy == HealingStrategy.AlwaysHeal else 'heal_left')
                self.wait(2)
            elif state == "on_pause":
                self.tap('resume')
                self.wait(2)
            elif state == "time_prize":
                self.tap("collect_time_prize")
                self.wait(5)
                self.tap("resume")
                self.wait(2)
            elif state == "endgame" or state == "repeat_endgame_question":
                if self.debug: print("React-Popups Endgame Detected")
                if state == "repeat_endgame_question":
                    if self.debug: print("state = repeat_endgame_question")
                if self.debug: print("You died or you won! Either way, game over!")
                self.log("You died or won!")
                self.log("Either way, it's over!")
                self.pressCloseEndgame()
                self.wait(2)
            elif state == "menu_home":
                raise Exception('mainscreen')
            i += 1
        return i

    def chooseBestAbility(self):
        abilities = self.screen_connector.getAbilityType()
        try:
            t1 = self.tier_list_abilities[abilities['l']]
            t2 = self.tier_list_abilities[abilities['c']]
            t3 = self.tier_list_abilities[abilities['r']]
            best = ""
            if t1 < t2 and t1 < t3:
                to_press = 'ability_left'
                best = abilities['l']
            if t2 < t1 and t2 < t3:
                to_press = 'ability_center'
                best = abilities['c']
            if t3 < t2 and t3 < t1:
                to_press = 'ability_right'
                best = abilities['r']
            if self.debug: print("Found best ability as " + best)
            self.log("Choosing '{}'".format(best))
            self.disableLogs = True
            self.tap(to_press)
            self.disableLogs = False
            self.wait(1) # wait for ability apply
        except Exception as e:
            if self.debug: print("Unable to correctly choose best ability. Randomly choosing left")
            self.log("Choosing 'Left Button'")
            self.disableLogs = True
            self.tap('ability_left')
            self.disableLogs = False
            self.wait(1) # wait for ability apply

    def intro_lvl(self):
        if self.debug: print("Getting Start Items")
        self.wait(8) # inital wait for ability wheel to load
        self.chooseBestAbility()
        self.swipe('n', 3)
        self.tap('lucky_wheel_start')
        self.wait(4)
        self.reactGamePopups()
        self.log("Leaving Start Room")
        self.swipe('n', 2)
        self.log("Entering Dungeon!")
        self.wait(1) # for GUI log to load

    def normal_lvl(self):
        if self.debug: print("normal_lvl")
        if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
            self.goTroughDungeon()
            self.letPlay(self.playtime)
            self.reactGamePopups()
            self.exit_dungeon_uncentered()
        else:
            self.reactGamePopups() # for efficency on 20+ level chapters 
            self.goTroughDungeon()
            self.reactGamePopups() # for efficency on 20+ level chapters
            self.letPlay(self.playtime)
            self.exit_dungeon_uncentered()

    def heal_lvl(self):
        if self.debug: print("heal_lvl")
        if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
            self.log("Approaching Healer")
            self.disableLogs = True
            self.swipe('n', 1.5)
            self.disableLogs = False
            self.reactGamePopups()
            self.swipe('n', .6)
            self.reactGamePopups()
            if self.debug: print("Exiting Heal")
            self.log("Leaving Healer")
            self.disableLogs = True
            self.swipe('n', 1)
            self.disableLogs = False
            self.log("Left Dungeon")
            self.wait(1)
        else:
            self.normal_lvl()

    def boss_lvl(self):
        if self.debug: print("boss_lvl")
        if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
            self.log("Attacking Boss")
            self.disableLogs = True
            self.swipe('n', 1.5)
            self.wait(2)
            self.swipe('e', .7)
            self.wait(2)
            self.swipe('nw', 2.5)
            self.wait(2)
            self.swipe('ne', 2.5)
            self.wait(2)
            self.swipe('w', .3)
            self.swipe('nw', .7)
            self.disableLogs = False
            self.letPlay(self.playtime, is_boss = True)
            self.reactGamePopups()
            self.log("Moving to Door")
            self.disableLogs = True
            self.swipe('s', .3)
            self.swipe('w', 1.5)
            self.swipe('n', 4)
            self.swipe('e', 1)
            self.disableLogs = False
            self.exit_dungeon_uncentered()
        else:
            self.normal_lvl()

    def boss_final(self):
        if self.debug: print("boss_final")
        if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
            state = self.screen_connector.getFrameState()
            self.log("Final Boss Appeared")
            self.log("Attacking Boss")
            self.swipe('w', 2)
            i = 0
            while i < self.max_wait:
                self.wait(self.sleep_btw_screens)
                if self.screen_connector.checkBoss3Died():
                    if self.debug: print("boss dead and door open #3")
                    self.log("Boss Dead")
                    break
                if self.screen_connector.checkBoss6Died():
                    if self.debug: print("boss dead and door open #6")
                    self.log("Boss Dead")
                    break
                if self.screen_connector.checkBoss10Died():
                    if self.debug: print("boss dead and door open #10")
                    self.log("Boss Dead")
                    break
                if self.debug: print(i)
                i += 1
            state = self.screen_connector.getFrameState()
            if self.debug: print("state: %s" % state)
            self.reactGamePopups()
            self.log("No Loot Left")
            if self.debug: print("Exiting the Dungeon Final Boss")
            self.log("Leaving Dungeon")
            self.disableLogs = True
            self.swipe('n', 5)
            self.swipe('ne', 3)
            self.disableLogs = False
            self.log("Left Dungeon!")
            self.wait(1) # for GUI log to load
            return
        else:
            self.normal_lvl()

    def start_one_game(self):
        i = 0
        while i <= self.max_loops_game:
            self.log("Checking conditions")
            self.log("Please wait...")
            self.screen_connector.checkDoorsOpen()
            self.start_date = datetime.now()
            self.screen_connector.stopRequested = False
            if self.debug: print("Checking for new_season")
            if self.screen_connector.checkFrame("popup_new_season"):
                if self.debug: print("Okay to New Season")
                self.log("Okay to New Season")
                self.tap("close_need_this")
                self.wait(5)
            if self.debug: print("Checking for patrol_reward")
            if self.screen_connector.checkFrame("popup_home_patrol"):
                if self.debug: print("Collecting time patrol")
                self.log("Collecting Time Patrol")
                self.tap("collect_hero_patrol")
                self.wait(5)
                self.tap("collect_hero_patrol")# click again somewhere to close popup with token things
            if self.debug: print("Checking for patrol_close")
            if self.screen_connector.checkFrame("btn_home_time_reward"):
                self.tap("close_hero_patrol")
                self.log("Closing Patrol")
                self.wait(5)
            if self.debug: print("Checking for vip_reward_1")
            if self.screen_connector.checkFrame("popup_vip_rewards"):
                if self.vip_priv_rewards:
                    if self.debug: print("Collecting VIP-Privilege Rewards 1")
                    self.log("VIP-Privilege Rewards 1")
                    self.tap("collect_vip_rewards")
                    self.wait(5)
                self.tap("close_vip_rewards")
                self.wait(5)
            if self.debug: print("Checking for vip_reward_2")
            if self.screen_connector.checkFrame("popup_vip_rewards"):
                if self.vip_priv_rewards:
                    if self.debug: print("Collecting VIP-Privilege Rewards 2")
                    self.log("VIP-Privilege Rewards 2")
                    self.tap("collect_vip_rewards")
                    self.wait(5)
                self.tap("close_vip_rewards")
                self.wait(5)
            if self.debug: print("Checking for need_this")
            if self.screen_connector.checkFrame("popup_need_this"):
                 if self.debug: print("Rejecting Must Need Ad")
                 self.log("Rejecting Must Need Ad")
                 self.tap("close_need_this")
                 self.wait(5)
            if self.debug: print("Checking for time_prize")
            if self.screen_connector.checkFrame("time_prize"):
                if self.debug: print("Collecting time prize")
                self.log("Collecting Time Prize")
                self.tap("collect_time_prize")
                self.wait(5)
                self.tap("resume")
                self.wait(2) 
            if self.currentLevel > 0:
                state = self.screen_connector.getFrameState()
                if self.debug: print("state: %s" % state)
                if state != 'in_game':
                    if self.debug: print("Something is not right, or you are not in a dungeon, trying again.")
                    self.log("Something is wrong")
                    self.log("Close all popups")
                    self.log("You must be in game")
                    self.log("at start of new room")
                    self.log("Trying level 0 now")
                    self.wait(1) # wait for logs to display
                    self.currentLevel = 0 # allows to continue playing if at home_menu      
            if self.currentLevel == 0:
                 if self.debug: print("Checking for energy")
                 while (not self.SkipEnergyCheck) and not self.screen_connector.checkFrame("least_5_energy"):
                    if self.debug: print("No energy, waiting for 60 minute")
                    self.log("No Energy")
                    self.noEnergyLeft.emit()
                    self.wait(3605) # wait for time to gain 5 energy        
            if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
                if self.debug: print("Selected Dungeon is 3/6/10")
                self.stat_lvl_start = self.currentLevel
            else:
                if self.debug: print("Selected Dungeon is *** NOT *** 3/6/10")
                if not self.screen_connector.checkFrame('endgame'):
                    self.currentLevel = 1 # allows to continue playing past 20+ levels
                    self.stat_lvl_start = self.currentLevel
                    if self.screen_connector.checkFrame('menu_home'):
                        self.currentLevel = 0 # allows to start playing 20+ levels
                        self.stat_lvl_start = self.currentLevel
            self.wait(6) # for GUI logs to sync
            print("New game. Starting from level %d" % self.currentLevel)
            self.log("New Game Started")
            try:
                if self.currentLevel == 0:
                    if self.debug: print("start_one_game level = 0")
                    self.chooseCave()
                else:
                    if self.debug: print("start_one_game level > 0")
                    self.play_cave()
            except Exception as exc:
                if exc.args[0] == 'mainscreen':
                    if self.debug: print("Main Menu. Restarting game now.")
                    self.log("Preparing to rest game")
                elif exc.args[0] == "unknown_screen_state":
                    if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
                        if self.debug: print("Unknows screen state. Exiting instead of doing trouble")
                        self.log("Unknown Screens... halp!")
                        self._exitEngine()
                    else:
                        if self.debug: print("Unknown State. Trying a game restart now.")
                elif exc.args[0] == "farm_loop_max":
                    if self.debug: print("Session End. Farming complete!")
                    self.log("Farming complete!")
                    self._exitEngine()
                else:
                    if self.debug: print("Got an unknown exception: %s" % exc)
                    self.log("Unknown Problem... halp!")
                    self._exitEngine()
            if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
                if self.debug: print("*** Saving Statistics #2 ***")
                self.statisctics_manager.saveOneGame(self.start_date, self.stat_lvl_start, self.currentLevel)      
            i += 1
            print(">>>>>>>>>>>>>>> Completed Farm Loop <<<<<<<<<<<<<<<")
            print(i)
        if i > self.max_loops_game:
            if self.debug: print("Max farming loops reached")
            raise Exception('farm_loop_max')
        
    def chooseCave(self):
        self.levelChanged.emit(self.currentLevel)
        if self.debug: print("Choosing Cave Start")
        self.log("Main Menu")
        self.tap('start')
        self.wait(2) # wait for no_raid button to load
        if self.debug: print("Checking for raid options")
        if self.screen_connector.checkFrame("quick_raid_option"):
            if self.debug: print("Choosing normal raid")
            self.tap('start_no_raid')
        self.play_cave()

    def play_cave(self):
        if self.currentLevel < 0 or self.currentLevel > 20:
            if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
                if self.debug: print("level out of range: %d" % self.currentLevel)
                self._exitEngine()
        while self.currentLevel <= self.max_level:
            print("***********************************")
            print("Level %d: %s" % (self.currentLevel, str(self.levels_type[self.currentLevel])))
            print("***********************************")
            if self.levels_type[self.currentLevel] == self.t_intro:
                self.intro_lvl()
            elif self.levels_type[self.currentLevel] == self.t_normal:
                self.normal_lvl()
            elif self.levels_type[self.currentLevel] == self.t_heal:
                self.heal_lvl()
            elif self.levels_type[self.currentLevel] == self.t_final_boss:
                self.boss_final()
            elif self.levels_type[self.currentLevel] == self.t_boss:
                self.boss_lvl()
            self.changeCurrentLevel(self.currentLevel + 1)
        self._manage_exit_from_endgame()
        if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
            if self.debug: print("*** Saving Statistics #1 ***")
            self.statisctics_manager.saveOneGame(self.start_date, self.stat_lvl_start, self.currentLevel)

    def _manage_exit_from_endgame(self): # for dungeons 3, 6, and 10
        if self.debug: print("manage_exit_from_endgame")
        self.wait(8) # wait for endgame loot screen to load
        state = self.screen_connector.getFrameState()
        if self.debug: print("state: %s" % state)
        if state == 'menu_home':
            return
        if state != 'endgame':
            self.tap('close_end') # maybe you leveled up trying to get endgame
            self.wait(8) # wait for endgame loot screen to load
        if state == 'endgame':
            if self.debug: print("Play-Cave. You won!")
            self.log("You won, Game over!")
            self.gameWon.emit()
            self.pressCloseEndgame()
        self.pressCloseEndIfEndedFrame()

    def pressCloseEndgame(self):
        if self.debug: print("Going back to main Menu")
        self.tap('close_end')
        self.currentLevel = 0
        self.wait(8) # wait for go back to main menu

    def pressCloseEndIfEndedFrame(self):
        if self.debug: print("pressCoseEndIfEndedFrame Check")
        state = self.screen_connector.getFrameState()
        if self.debug: print("state: %s" % state)
        if state == 'endgame':
            self.pressCloseEndgame()
            self.wait(8) # wait for go back to main menu

    def _exitEngine(self):
        print ("Game Engine Closed")
        if self.currentDungeon == 3 or self.currentDungeon == 6 or self.currentDungeon == 10:
            if self.debug: print("*** Saving Statistics #4 ***")
            self.statisctics_manager.saveOneGame(self.start_date, self.stat_lvl_start, self.currentLevel)
        exit(1)
