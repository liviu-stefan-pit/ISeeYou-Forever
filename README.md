# ISeeYou-Forever

This is a World of Warcraft addon that writes down what you do while you level. It remembers quests, gold, experience, where you walked, fights, and deaths. After you log out, a small program turns that into a journal you can open and read.

It starts from the level you are when you first log in with the addon on. If you are level 12, it does not know what you did from level 1 to 11.

## What you need

- World of Warcraft (this copy looks in the Classic Beta folder)
- Python 3 installed on your computer. In a command window, `py -3` should work.

## 1. Put the addon in the game

1. Find your game folder. The usual place is:

   `C:\Program Files (x86)\World of Warcraft\_classic_beta_`

2. Open `Interface`, then `AddOns`. If those folders are missing, make them.
3. Copy the `ISeeYouForever` folder from this project into `AddOns`.

   You should end up with:

   `...\Interface\AddOns\ISeeYouForever\ISeeYouForever.toc`

4. Start the game. On the character screen, click **AddOns** and make sure **I see you forever** is checked.

## 2. Log in and let it record

Log in on the character you want to track. You should see a line in chat that says it is recording, and from which level.

Play normally. You do not have to press anything while you quest.

The game only saves the notes when you **log out** or type `/reload`. If you close the game with the power button, the last few minutes can be missing.

## 3. Turn the notes into the journal

The addon cannot write the journal by itself. You run one of these after you log out.

**Easiest:** log out, then double-click `export-wiki.bat` in this project folder. Wait until it says it wrote your character and cleared the game save, then press a key to close the window.

When that export succeeds, the bat deletes the copied notes from the game's save. The journal keeps them. Your `/isy` settings stay, including the wiki folder and which boxes are checked. The next login starts a new set of notes. Log out before you run it. If the game is still open, it can write the old notes back over the cleared save when you leave.

**While you play:** open a command window in this project folder and run:

```
py -3 tools\watch_wiki.py
```

Leave that window open. A few seconds after each logout or `/reload`, it updates the journal and leaves the game save alone. Close the window when you are done for the day. Run `export-wiki.bat` when you want those notes removed from the game save.

### Choose where the journal is saved

The journal is your own pages. This project does not ship anyone's characters. You pick the folder, and the exporter creates it if it is missing.

**In the game, this is the setting that sticks:**

1. Log in and type `/isy`, then press Enter.
2. At the bottom of the window, find **Wiki folder**.
3. Paste the full path of the folder you want. Example: `D:\wow-journal`
4. Press Enter. Chat confirms the folder was saved.

Leave **Wiki folder** empty to use the `wiki` folder next to this README.

WoW saves that path with the addon. It does not write the pages. The next logout or `/reload` is when `export-wiki.bat` or the watcher reads the path and writes the journal there. The same path is used every time after that, until you change the box and press Enter again.

The exporter also writes a `data` folder beside the journal folder. If the journal is `D:\wow-journal`, the database and the `check.md` notes go in `D:\data`.

**From the command line**, you can name both folders. The first is the game's `WTF` folder. The second is the journal folder:

```
py -3 tools\watch_wiki.py "D:\Games\World of Warcraft\_classic_beta_\WTF" "D:\wow-journal"
```

If **Wiki folder** in `/isy` already has a path, that path wins. The second argument is used only when the box is empty. `export-wiki.bat` follows the same rule: the `/isy` path, or this project's `wiki` folder when the box is empty.

After the first export, open the folder you chose:

- `index.md` is the list of characters.
- `dashboard.html` is one page of charts: level over time, experience per hour, where the time went, gold by source, deaths, and quest efficiency. Open it in a browser. It does not need the internet.
- Open a character, then open a level chapter such as `1-10`.
- `log` is the raw diary. Do not edit those files. The other pages are rebuilt from them.

`wiki\SCHEMA.md` in this project only describes the page layout. Your characters are written into the folder you configured.

## 4. The /isy window

In game, type `/isy` and press Enter. A window opens. You can also click the addon button on the minimap menu.

The top line shows this session: how long you have played, experience gained, and gold in and out.

Every box is something the addon writes down. Leave them all checked unless you know you do not want one of them.

| Box | What it writes down |
| --- | --- |
| Experience and level-ups | Experience ticks and each time you ding |
| Quests | Who gave the quest, where you did it, and who you handed it to |
| Money | Gold you gain and spend |
| Routes | Dots on the map as you walk |
| Zones and travel | When you change zone, hearth, or take a flight |
| Fights | How long each fight lasted and the experience from it |
| Mob identity | The name, level, and type of what you fight |
| Deaths | Where you died |
| Loot | Items you pick up |
| Skills | When a skill goes up |
| Reputation | Faction standing changes |
| Bags | What is in your bags at login, level-up, and logout, plus changes in between |
| Group size | Whether you are alone or in a group |
| Character, talents, and gear | Class, race, talent points, and what you have equipped |
| NPCs | Vendors, trainers, and quest givers you talk to |
| Activity | Resting, AFK, and being on a mount |

**Wiki folder** is the path from the section above. Paste a full folder path and press Enter, or leave it empty for this project's `wiki` folder. The next logout writes the journal there.

**All on** and **All off** check or uncheck every box.

**Show logger** shows or hides the live logger. **Lock logger** stops it from being dragged or resized. **Show route dots** adds the map samples to the logger. Those samples are written every few seconds while you walk, so they stay off unless you want them. **Show rates** turns the experience line on the logger on or off. It is on until you uncheck it.

## 5. The live logger

A small window sits on the screen while you play. It lists the last 10 things the addon wrote down, in plain words, with the time on the left. The top right shows how many notes are waiting in the save.

Under the title, a line shows experience per hour from the last 15 minutes (or the whole session, if that window is still empty), about how long until the next level, rested experience still in the pool, and how much of this session's experience came from quests versus kills.

Drag the window to move it. Drag the corner to resize it. Right-click it to open `/isy`. The place and size are remembered for every character on the account.

`/isy log` shows or hides it. `/isy reset` puts it back in the middle at the default size and unlocks it.

The logger only displays what is already recorded. It does not save, reload, or write the journal. Log out or `/reload` as before, then let the watcher or `export-wiki.bat` update the journal.

## If something looks wrong

Open `data\characters\<your character>\check.md`. It lists problems in the recording, such as a missing zone name at login. The journal pages try to fix the obvious ones. The `check` file tells you what the raw notes actually said.
