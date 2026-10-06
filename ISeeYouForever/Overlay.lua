local addonName, ns = ...

local LINES = 10
local DEFAULT_WIDTH = 320
local DEFAULT_HEIGHT = 170
local MIN_WIDTH = 180
local MIN_HEIGHT = 90
local MAX_WIDTH = 700
local MAX_HEIGHT = 480

local SLOTS = {
    [1] = "Head",
    [2] = "Neck",
    [3] = "Shoulder",
    [4] = "Shirt",
    [5] = "Chest",
    [6] = "Waist",
    [7] = "Legs",
    [8] = "Feet",
    [9] = "Wrist",
    [10] = "Hands",
    [11] = "Ring",
    [12] = "Ring",
    [13] = "Trinket",
    [14] = "Trinket",
    [15] = "Back",
    [16] = "Main hand",
    [17] = "Off hand",
    [18] = "Ranged",
    [19] = "Tabard",
}

local COLOR = {
    xp = "ffd100",
    level = "ffd100",
    quest_accept = "7dff7d",
    quest_seen = "7dff7d",
    quest_progress = "7dff7d",
    quest_ready = "7dff7d",
    quest_turnin = "7dff7d",
    quest_abandon = "ff8080",
    money = "ffcc33",
    loot = "ffffff",
    fight_start = "ff6666",
    fight_end = "ff6666",
    kill = "ff6666",
    mob = "ff8888",
    death = "ff4040",
    unghost = "ff8080",
    alive = "7dff7d",
    zone = "80dfff",
    travel = "80dfff",
    taxi_start = "80dfff",
    taxi_end = "80dfff",
    bind = "80dfff",
    route = "8a8a8a",
    rep = "c9a0ff",
    skill = "c9a0ff",
    spell_learned = "c9a0ff",
    npc = "f0d080",
    npc_close = "f0d080",
    gear = "f0d080",
    character = "f0d080",
    group = "d0d0d0",
    rest = "d0d0d0",
    afk = "d0d0d0",
    mount = "d0d0d0",
    bags = "d0d0d0",
    bag_delta = "d0d0d0",
    session_start = "ffffff",
    session_end = "ffffff",
    played = "aaaaaa",
}

local frame
local log
local countText
local statsText
local grip

local function cell(fields, index)
    local value = fields and fields[index]
    if value == nil or ns.IsSecret(value) then
        return ""
    end
    return tostring(value)
end

local function flagOn(value)
    return value == "1" or value == "true"
end

local function signedCopper(value)
    local amount = tonumber(value) or 0
    if amount > 0 then
        return "+" .. ns.FormatCopper(amount)
    end
    return ns.FormatCopper(amount)
end

local function shortSeconds(value)
    local amount = tonumber(value)
    if not amount then
        return cell({ value }, 1)
    end
    if amount == math.floor(amount) then
        return tostring(math.floor(amount))
    end
    return string.format("%.1f", amount)
end

local function place(zone, sub)
    if zone ~= "" and sub ~= "" and sub ~= zone then
        return zone .. " - " .. sub
    end
    if zone ~= "" then
        return zone
    end
    return sub
end

local function xpLine(fields)
    local amount = tonumber(cell(fields, 1)) or 0
    local source = cell(fields, 4)
    local mob = cell(fields, 5)
    local mobLevel = cell(fields, 6)
    local head = "XP +" .. tostring(amount)
    if mob ~= "" then
        if mobLevel ~= "" then
            return head .. "  " .. mob .. " (" .. mobLevel .. ")"
        end
        return head .. "  " .. mob
    end
    if source ~= "" and source ~= "other" then
        return head .. "  " .. source
    end
    return head
end

local function questLine(verb, fields)
    local title = cell(fields, 2)
    if title == "" then
        title = cell(fields, 1)
    end
    return "Quest " .. verb .. ": " .. title
end

local function lootLine(fields)
    local message = cell(fields, 1)
    local link = string.match(message, "(|c%x+|Hitem:.-|h%[.-%]|h|r)")
    if not link then
        link = string.match(message, "(%[.-%])")
    end
    local count = cell(fields, 3)
    local extra = ""
    if count ~= "" and count ~= "1" then
        extra = " x" .. count
    end
    if link then
        return "Loot  " .. link .. extra
    end
    if message ~= "" then
        return "Loot  " .. message
    end
    return "Loot"
end

local function fightEndLine(fields)
    local duration = shortSeconds(cell(fields, 1))
    local xp = tonumber(cell(fields, 2)) or 0
    if xp > 0 then
        return "Fight " .. duration .. "s, +" .. tostring(xp) .. " XP"
    end
    return "Fight " .. duration .. "s"
end

local function travelLine(fields)
    local method = cell(fields, 1)
    local origin = cell(fields, 2)
    local dest = cell(fields, 3)
    if method == "hearth" then
        if dest ~= "" then
            return "Hearth to " .. dest
        end
        if origin ~= "" then
            return "Hearth from " .. origin
        end
        return "Hearth"
    end
    if method == "taxi" then
        if origin ~= "" and dest ~= "" then
            return "Flew from " .. origin .. " to " .. dest
        end
        if dest ~= "" then
            return "Flew to " .. dest
        end
    end
    if dest ~= "" then
        return "Traveled to " .. dest
    end
    if origin ~= "" then
        return "Traveled to " .. origin
    end
    return "Traveled"
end

local function changeCount(text)
    if text == "" then
        return 0
    end
    local count = 1
    for _ in string.gmatch(text, ",") do
        count = count + 1
    end
    return count
end

local LINES_OF = {
    xp = xpLine,
    level = function(fields)
        return "Level " .. cell(fields, 1)
    end,
    quest_accept = function(fields)
        return questLine("accepted", fields)
    end,
    quest_seen = function(fields)
        return questLine("already had", fields)
    end,
    quest_ready = function(fields)
        return questLine("ready", fields)
    end,
    quest_turnin = function(fields)
        local line = questLine("done", fields)
        local xp = tonumber(cell(fields, 3)) or 0
        if xp > 0 then
            return line .. "  +" .. tostring(xp) .. " XP"
        end
        return line
    end,
    quest_abandon = function(fields)
        return questLine("abandoned", fields)
    end,
    quest_progress = function(fields)
        local title = cell(fields, 2)
        local objective = cell(fields, 3)
        local done = cell(fields, 4)
        local required = cell(fields, 5)
        local progress = ""
        if done ~= "" or required ~= "" then
            progress = " " .. done .. "/" .. required
        end
        if title ~= "" and objective ~= "" then
            return "Quest " .. title .. ": " .. objective .. progress
        end
        return "Quest progress" .. progress
    end,
    money = function(fields)
        local source = cell(fields, 3)
        local line = "Money " .. signedCopper(cell(fields, 1))
        if source ~= "" then
            return line .. " (" .. source .. ")"
        end
        return line
    end,
    loot = lootLine,
    skill = function(fields)
        local message = cell(fields, 1)
        if message ~= "" then
            return message
        end
        return "Skill up"
    end,
    spell_learned = function(fields)
        local name = cell(fields, 2)
        if name ~= "" then
            return "Learned " .. name
        end
        return "Learned a spell"
    end,
    rep = function(fields)
        local name = cell(fields, 1)
        local reaction = cell(fields, 2)
        local standing = cell(fields, 3)
        local line = "Rep"
        if name ~= "" then
            line = line .. " " .. name
        end
        if reaction ~= "" then
            line = line .. " " .. reaction
        end
        if standing ~= "" then
            line = line .. " " .. standing
        end
        return line
    end,
    death = function(fields)
        local zone = cell(fields, 1)
        if zone ~= "" then
            return "Died in " .. zone
        end
        return "Died"
    end,
    unghost = function(fields)
        local zone = cell(fields, 1)
        if zone ~= "" then
            return "Released in " .. zone
        end
        return "Released"
    end,
    alive = function(fields)
        local zone = cell(fields, 1)
        if zone ~= "" then
            return "Alive in " .. zone
        end
        return "Alive"
    end,
    zone = function(fields)
        local where = place(cell(fields, 1), cell(fields, 2))
        if where ~= "" then
            return "Zone " .. where
        end
        return "Zone changed"
    end,
    travel = travelLine,
    taxi_start = function(fields)
        local dest = cell(fields, 2)
        if dest ~= "" then
            return "Flight to " .. dest
        end
        return "Flight started"
    end,
    taxi_end = function(fields)
        local zone = cell(fields, 2)
        if zone ~= "" then
            return "Landed in " .. zone
        end
        return "Landed"
    end,
    bind = function(fields)
        local where = place(cell(fields, 1), cell(fields, 2))
        if where ~= "" then
            return "Hearth set to " .. where
        end
        return "Hearth set"
    end,
    route = function(fields)
        local zone = cell(fields, 4)
        if zone ~= "" then
            return "Route " .. zone
        end
        return "Route"
    end,
    fight_start = function(fields)
        local name = cell(fields, 5)
        local level = cell(fields, 6)
        if name ~= "" and level ~= "" then
            return "Fight " .. name .. " (" .. level .. ")"
        end
        if name ~= "" then
            return "Fight " .. name
        end
        return "Fight started"
    end,
    fight_end = fightEndLine,
    kill = function(fields)
        local name = cell(fields, 1)
        local level = cell(fields, 3)
        if name ~= "" and level ~= "" then
            return "Kill " .. name .. " (" .. level .. ")"
        end
        if name ~= "" then
            return "Kill " .. name
        end
        return "Kill"
    end,
    mob = function(fields)
        local name = cell(fields, 1)
        local level = cell(fields, 2)
        if name ~= "" and level ~= "" then
            return "Mob " .. name .. " (" .. level .. ")"
        end
        if name ~= "" then
            return "Mob " .. name
        end
        return "Mob"
    end,
    npc = function(fields)
        local kind = cell(fields, 1)
        local name = cell(fields, 2)
        if name ~= "" and kind ~= "" then
            return "NPC " .. kind .. " " .. name
        end
        if name ~= "" then
            return "NPC " .. name
        end
        if kind ~= "" then
            return "NPC " .. kind
        end
        return "NPC"
    end,
    npc_close = function(fields)
        local kind = cell(fields, 1)
        local duration = cell(fields, 2)
        local line = "Left"
        if kind ~= "" then
            line = line .. " " .. kind
        end
        if duration ~= "" then
            return line .. " (" .. shortSeconds(duration) .. "s)"
        end
        return line
    end,
    gear = function(fields)
        local slot = tonumber(cell(fields, 1))
        local name = slot and SLOTS[slot]
        if name then
            return "Gear " .. name
        end
        return "Gear changed"
    end,
    character = function(fields)
        local className = cell(fields, 2)
        local reason = cell(fields, 9)
        if className ~= "" and reason ~= "" then
            return "Character " .. className .. " (" .. reason .. ")"
        end
        if reason ~= "" then
            return "Character " .. reason
        end
        return "Character"
    end,
    group = function(fields)
        local size = tonumber(cell(fields, 1)) or 1
        if size <= 1 then
            return "Alone"
        end
        return "Group of " .. tostring(size)
    end,
    rest = function(fields)
        if flagOn(cell(fields, 1)) then
            return "Resting"
        end
        return "Not resting"
    end,
    afk = function(fields)
        if flagOn(cell(fields, 1)) then
            return "AFK"
        end
        return "Back"
    end,
    mount = function(fields)
        if flagOn(cell(fields, 1)) then
            return "Mounted"
        end
        return "Dismounted"
    end,
    bags = function()
        return "Bags recorded"
    end,
    bag_delta = function(fields)
        local count = changeCount(cell(fields, 1))
        if count == 1 then
            return "Bags changed (1 item)"
        end
        return "Bags changed (" .. tostring(count) .. " items)"
    end,
    session_start = function(fields)
        local level = cell(fields, 1)
        local where = place(cell(fields, 2), cell(fields, 3))
        local line = "Recording"
        if level ~= "" then
            line = line .. " from level " .. level
        end
        if where ~= "" then
            line = line .. " in " .. where
        end
        return line
    end,
    session_end = function(fields)
        local duration = tonumber(cell(fields, 2))
        if duration then
            return "Session ended, " .. ns.FormatDuration(duration)
        end
        return "Session ended"
    end,
    played = function(fields)
        local total = tonumber(cell(fields, 1))
        if total then
            return "Played " .. ns.FormatDuration(total)
        end
        return "Played"
    end,
}

local function fallback(kind, fields)
    local bits = { kind }
    local used = 0
    for i = 1, #fields do
        local value = cell(fields, i)
        if value ~= "" then
            used = used + 1
            if used > 4 then
                break
            end
            if #value > 40 then
                value = string.sub(value, 1, 40)
            end
            bits[#bits + 1] = value
        end
    end
    return table.concat(bits, " ")
end

function ns.DescribeEvent(kind, fields)
    local writer = LINES_OF[kind]
    if writer then
        return writer(fields or {})
    end
    return fallback(kind or "event", fields or {})
end

local function splitTabs(text)
    local out = {}
    local startAt = 1
    while true do
        local tab = string.find(text, "\t", startAt, true)
        if not tab then
            out[#out + 1] = string.sub(text, startAt)
            return out
        end
        out[#out + 1] = string.sub(text, startAt, tab - 1)
        startAt = tab + 1
    end
end

local function ensureOverlay()
    if type(ISYF_DB) ~= "table" then
        ISYF_DB = {}
    end
    if type(ISYF_DB.overlay) ~= "table" then
        ISYF_DB.overlay = {}
    end
    return ISYF_DB.overlay
end

function ns.LoggerShown()
    local overlay = ISYF_DB and ISYF_DB.overlay
    if type(overlay) == "table" and overlay.shown ~= nil then
        return overlay.shown and true or false
    end
    return true
end

function ns.LoggerLocked()
    local overlay = ISYF_DB and ISYF_DB.overlay
    return type(overlay) == "table" and overlay.locked and true or false
end

function ns.LoggerRoutes()
    local overlay = ISYF_DB and ISYF_DB.overlay
    return type(overlay) == "table" and overlay.routes and true or false
end

function ns.LoggerStats()
    local overlay = ISYF_DB and ISYF_DB.overlay
    if type(overlay) == "table" and overlay.stats ~= nil then
        return overlay.stats and true or false
    end
    return true
end

local function countLabel()
    local total = 0
    if ISYF_Char and type(ISYF_Char.events) == "table" then
        total = #ISYF_Char.events
    end
    local text = tostring(total)
    if type(BreakUpLargeNumbers) == "function" then
        local ok, formatted = pcall(BreakUpLargeNumbers, total)
        if ok and type(formatted) == "string" then
            text = formatted
        end
    end
    if total == 1 then
        return text .. " event"
    end
    return text .. " events"
end

local function groupedNumber(value)
    local number = math.floor((tonumber(value) or 0) + 0.5)
    if type(BreakUpLargeNumbers) == "function" then
        local ok, formatted = pcall(BreakUpLargeNumbers, number)
        if ok and type(formatted) == "string" then
            return formatted
        end
    end
    return tostring(number)
end

local function ratesLabel()
    if not ns.LoggerStats() or not ns.SessionRates then
        return ""
    end
    local rates = ns.SessionRates()
    if not rates then
        return ""
    end
    local eta = "waiting"
    if rates.eta and rates.eta > 0 then
        eta = ns.FormatDuration(rates.eta) .. " to " .. tostring(rates.nextLevel)
    end
    local split = ""
    if rates.hasSplit then
        split = string.format("  |  quest %d%% / kill %d%%", rates.questPct, rates.killPct)
    end
    return string.format(
        "%s XP/hr  |  %s  |  rested %s%s",
        groupedNumber(rates.rate),
        eta,
        groupedNumber(rates.rested),
        split
    )
end

local function layoutLog()
    if not log then
        return
    end
    local top = -28
    if statsText then
        if ns.LoggerStats() then
            statsText:Show()
            top = -44
        else
            statsText:Hide()
        end
    end
    log:ClearAllPoints()
    log:SetPoint("TOPLEFT", 10, top)
    log:SetPoint("BOTTOMLEFT", 10, 8)
    log:SetWidth(math.max(40, (frame and frame:GetWidth() or DEFAULT_WIDTH) - 24))
end

function ns.RefreshOverlay()
    if not countText then
        return
    end
    countText:SetText(countLabel())
    if statsText then
        statsText:SetText(ratesLabel())
        layoutLog()
    end
end

local function formatLine(kind, fields, when)
    local body = ns.DescribeEvent(kind, fields)
    if not body or body == "" then
        return nil
    end
    local stamp = date("%H:%M", when or time())
    local color = COLOR[kind] or "ffffff"
    return string.format("|cffaaaaaa%s|r  |cff%s%s|r", stamp, color, body)
end

local function fieldsOf(parts)
    local fields = {}
    for i = 5, #parts do
        fields[#fields + 1] = parts[i]
    end
    return fields
end

local function refill()
    if not log then
        return
    end
    log:Clear()
    local events = ISYF_Char and ISYF_Char.events
    if type(events) ~= "table" then
        ns.RefreshOverlay()
        return
    end
    local picked = {}
    local showRoutes = ns.LoggerRoutes()
    for i = #events, 1, -1 do
        local row = events[i]
        if type(row) == "string" then
            local parts = splitTabs(row)
            local kind = parts[4]
            if kind and kind ~= "" and (kind ~= "route" or showRoutes) then
                picked[#picked + 1] = parts
                if #picked >= LINES then
                    break
                end
            end
        end
    end
    for i = #picked, 1, -1 do
        local parts = picked[i]
        local when = tonumber(parts[2]) or time()
        local line = formatLine(parts[4], fieldsOf(parts), when)
        if line then
            log:AddMessage(line)
        end
    end
    log:ScrollToBottom()
    ns.RefreshOverlay()
end

local function saveLayout()
    if not frame then
        return
    end
    local point, _, relative, x, y = frame:GetPoint(1)
    local overlay = ensureOverlay()
    overlay.point = point or "CENTER"
    overlay.rel = relative or point or "CENTER"
    overlay.x = x or 0
    overlay.y = y or 0
    overlay.width = frame:GetWidth()
    overlay.height = frame:GetHeight()
end

local function applyLayout()
    if not frame then
        return
    end
    local overlay = ensureOverlay()
    local width = tonumber(overlay.width) or DEFAULT_WIDTH
    local height = tonumber(overlay.height) or DEFAULT_HEIGHT
    if width < MIN_WIDTH then
        width = MIN_WIDTH
    elseif width > MAX_WIDTH then
        width = MAX_WIDTH
    end
    if height < MIN_HEIGHT then
        height = MIN_HEIGHT
    elseif height > MAX_HEIGHT then
        height = MAX_HEIGHT
    end
    frame:ClearAllPoints()
    frame:SetPoint(
        overlay.point or "CENTER",
        UIParent,
        overlay.rel or overlay.point or "CENTER",
        tonumber(overlay.x) or 0,
        tonumber(overlay.y) or 120
    )
    frame:SetSize(width, height)
end

local function applyChrome()
    if not frame then
        return
    end
    if ns.LoggerLocked() then
        grip:Hide()
    else
        grip:Show()
    end
end

local function syncChecks()
    if ns.RefreshLoggerChecks then
        ns.RefreshLoggerChecks()
    end
end

function ns.SetLoggerShown(on)
    local overlay = ensureOverlay()
    overlay.shown = on and true or false
    if frame then
        if overlay.shown then
            frame:Show()
        else
            frame:Hide()
        end
    end
    syncChecks()
end

function ns.SetLoggerLocked(on)
    local overlay = ensureOverlay()
    overlay.locked = on and true or false
    applyChrome()
    syncChecks()
end

function ns.SetLoggerRoutes(on)
    local overlay = ensureOverlay()
    overlay.routes = on and true or false
    refill()
    syncChecks()
end

function ns.SetLoggerStats(on)
    local overlay = ensureOverlay()
    overlay.stats = on and true or false
    ns.RefreshOverlay()
    syncChecks()
end

function ns.ToggleLogger()
    ns.SetLoggerShown(not ns.LoggerShown())
end

function ns.ResetLogger()
    local overlay = ensureOverlay()
    overlay.point = "CENTER"
    overlay.rel = "CENTER"
    overlay.x = 0
    overlay.y = 120
    overlay.width = DEFAULT_WIDTH
    overlay.height = DEFAULT_HEIGHT
    overlay.locked = false
    overlay.shown = true
    applyLayout()
    applyChrome()
    if frame then
        frame:Show()
    end
    syncChecks()
end

function ns.LogLive(kind, fields, when)
    local ok, err = pcall(function()
        ns.RefreshOverlay()
        if not log or not kind then
            return
        end
        if kind == "route" and not ns.LoggerRoutes() then
            return
        end
        local line = formatLine(kind, fields, when)
        if not line then
            return
        end
        log:AddMessage(line)
        log:ScrollToBottom()
    end)
    if not ok then
        ns.Print("Logger failed: " .. tostring(err))
    end
end

local function onDragStart()
    if ns.LoggerLocked() or not frame then
        return
    end
    frame:StartMoving()
end

local function onDragStop()
    if not frame then
        return
    end
    frame:StopMovingOrSizing()
    saveLayout()
end

local function onRightClick(_, button)
    if button == "RightButton" and ns.Toggle then
        ns.Toggle()
    end
end

local function buildFrame()
    local ok, created = pcall(CreateFrame, "Frame", nil, UIParent, "BackdropTemplate")
    if not ok or not created then
        created = CreateFrame("Frame", nil, UIParent)
    end
    frame = created
    frame:SetSize(DEFAULT_WIDTH, DEFAULT_HEIGHT)
    frame:SetFrameStrata("MEDIUM")
    frame:SetMovable(true)
    frame:SetResizable(true)
    frame:EnableMouse(true)
    frame:RegisterForDrag("LeftButton")
    frame:SetClampedToScreen(true)
    frame:SetScript("OnDragStart", onDragStart)
    frame:SetScript("OnDragStop", onDragStop)
    frame:SetScript("OnMouseUp", onRightClick)
    if frame.SetResizeBounds then
        frame:SetResizeBounds(MIN_WIDTH, MIN_HEIGHT, MAX_WIDTH, MAX_HEIGHT)
    else
        frame:SetMinResize(MIN_WIDTH, MIN_HEIGHT)
        frame:SetMaxResize(MAX_WIDTH, MAX_HEIGHT)
    end
    if frame.SetBackdrop then
        frame:SetBackdrop({
            bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
            edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
            tile = true,
            tileSize = 16,
            edgeSize = 12,
            insets = { left = 3, right = 3, top = 3, bottom = 3 },
        })
        frame:SetBackdropColor(0, 0, 0, 0.65)
        frame:SetBackdropBorderColor(0.35, 0.35, 0.35, 0.9)
    end

    local title = frame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    title:SetPoint("TOPLEFT", 10, -8)
    title:SetJustifyH("LEFT")
    title:SetText("I see you forever")

    countText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    countText:SetPoint("TOPRIGHT", -10, -9)
    countText:SetJustifyH("RIGHT")
    title:SetPoint("RIGHT", countText, "LEFT", -8, 0)

    statsText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    statsText:SetPoint("TOPLEFT", 10, -26)
    statsText:SetPoint("TOPRIGHT", -10, -26)
    statsText:SetJustifyH("LEFT")
    statsText:SetText("")

    log = CreateFrame("ScrollingMessageFrame", nil, frame)
    log:SetPoint("TOPLEFT", 10, -44)
    log:SetPoint("BOTTOMLEFT", 10, 8)
    log:SetFontObject(GameFontHighlightSmall)
    log:SetJustifyH("LEFT")
    log:SetFading(false)
    log:SetMaxLines(LINES)
    if log.SetInsertMode then
        log:SetInsertMode("BOTTOM")
    end
    log:EnableMouse(true)
    log:EnableMouseWheel(true)
    log:RegisterForDrag("LeftButton")
    log:SetScript("OnDragStart", onDragStart)
    log:SetScript("OnDragStop", onDragStop)
    log:SetScript("OnMouseUp", onRightClick)
    log:SetScript("OnMouseWheel", function(self, delta)
        if delta > 0 then
            self:ScrollUp()
        else
            self:ScrollDown()
        end
    end)
    frame:SetScript("OnSizeChanged", function(self, width)
        log:SetWidth(math.max(40, (width or self:GetWidth()) - 24))
    end)

    grip = CreateFrame("Button", nil, frame)
    grip:SetSize(16, 16)
    grip:SetPoint("BOTTOMRIGHT", -2, 2)
    grip:SetFrameLevel(frame:GetFrameLevel() + 5)
    grip:SetNormalTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Up")
    grip:SetHighlightTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Highlight")
    grip:SetPushedTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Down")
    grip:RegisterForDrag("LeftButton")
    grip:SetScript("OnDragStart", function()
        if ns.LoggerLocked() then
            return
        end
        frame:StartSizing("BOTTOMRIGHT")
    end)
    grip:SetScript("OnDragStop", function()
        frame:StopMovingOrSizing()
        saveLayout()
    end)

    applyLayout()
    log:SetWidth(math.max(40, frame:GetWidth() - 24))
    applyChrome()
    layoutLog()
    ns.RefreshOverlay()
    refill()
    if C_Timer and C_Timer.NewTicker then
        C_Timer.NewTicker(5, function()
            ns.RefreshOverlay()
        end)
    end
    if ns.LoggerShown() then
        frame:Show()
    else
        frame:Hide()
    end
end

function ns.InitOverlay()
    if frame then
        return
    end
    buildFrame()
end
