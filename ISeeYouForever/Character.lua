local addonName, ns = ...

local pendingReason
local pendingCharacter = false

local function classToken()
    if type(UnitClass) ~= "function" then
        return ""
    end
    local ok, _, token = pcall(UnitClass, "player")
    if not ok then
        return ""
    end
    return ns.Str(token) or ""
end

local function raceToken()
    if type(UnitRace) ~= "function" then
        return ""
    end
    local ok, _, token = pcall(UnitRace, "player")
    if not ok then
        return ""
    end
    return ns.Str(token) or ""
end

local function factionToken()
    if type(UnitFactionGroup) ~= "function" then
        return ""
    end
    local ok, faction = pcall(UnitFactionGroup, "player")
    if not ok then
        return ""
    end
    return ns.Str(faction) or ""
end

local function talentSummary()
    local parts = {}
    local count = 0
    if type(GetNumTalentTabs) == "function" then
        local ok, total = pcall(GetNumTalentTabs)
        if ok then
            count = ns.Num(total) or 0
        end
    end
    for index = 1, count do
        local ok, a, b, c, _, e = pcall(GetTalentTabInfo, index)
        if ok then
            local name = ns.Str(a)
            local points = ns.Num(c)
            if not name then
                name = ns.Str(b)
                points = ns.Num(e)
            end
            if name then
                parts[#parts + 1] = name .. ":" .. tostring(points or 0)
            end
        end
    end
    return table.concat(parts, ",")
end

function ns.CaptureGear()
    ns.gearSlots = {}
    if type(GetInventoryItemID) ~= "function" then
        return ""
    end
    local parts = {}
    for slot = 1, 19 do
        local ok, itemId = pcall(GetInventoryItemID, "player", slot)
        local stored = ""
        if ok then
            local number = ns.Num(itemId)
            if number then
                stored = tostring(number)
                parts[#parts + 1] = tostring(slot) .. ":" .. stored
            end
        end
        ns.gearSlots[slot] = stored
    end
    return table.concat(parts, ",")
end

local function emitNow(reason)
    if not ns.sessionOpen and reason ~= "login" then
        return
    end
    local guid = ""
    if type(UnitGUID) == "function" then
        local ok, value = pcall(UnitGUID, "player")
        if ok then
            guid = ns.Str(value) or ""
        end
    end
    local sex = 0
    if type(UnitSex) == "function" then
        sex = ns.Num(UnitSex("player")) or 0
    end
    local level = ns.Num(UnitLevel("player")) or ns.lastLevel or 0
    local gear = ns.CaptureGear()
    ns.Emit(
        "character",
        "character",
        guid,
        classToken(),
        raceToken(),
        factionToken(),
        sex,
        level,
        talentSummary(),
        gear,
        reason or ""
    )
end

function ns.EmitCharacter(reason)
    if reason == "login" then
        emitNow("login")
        return
    end
    pendingReason = reason or pendingReason or ""
    if pendingCharacter then
        return
    end
    pendingCharacter = true
    ns.After(0.3, function()
        pendingCharacter = false
        local why = pendingReason or ""
        pendingReason = nil
        emitNow(why)
    end)
end

function ns.InitCharacter()
    local function onTalents()
        if ns.sessionOpen and ns.sessionStarted then
            ns.EmitCharacter("talents")
        end
    end

    ns.Register("CHARACTER_POINTS_CHANGED", onTalents)
    ns.Register("PLAYER_TALENT_UPDATE", onTalents)

    ns.Register("PLAYER_EQUIPMENT_CHANGED", function(_, slot)
        if not ns.sessionOpen or not ns.sessionStarted then
            return
        end
        slot = ns.Num(slot)
        if not slot then
            return
        end
        local previous = (ns.gearSlots and ns.gearSlots[slot]) or ""
        local current = ""
        if type(GetInventoryItemID) == "function" then
            local ok, itemId = pcall(GetInventoryItemID, "player", slot)
            if ok then
                local number = ns.Num(itemId)
                if number then
                    current = tostring(number)
                end
            end
        end
        if current == previous then
            return
        end
        ns.gearSlots = ns.gearSlots or {}
        ns.gearSlots[slot] = current
        ns.Emit("gear", "character", slot, previous, current)
    end)
end
