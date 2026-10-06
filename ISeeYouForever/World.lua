local addonName, ns = ...

local repSeeded = false
local repCache = {}
local lastBag = nil
local bagCounts = nil

local function readBags()
    local counts = {}
    local ids = {}
    if not C_Container or not C_Container.GetContainerNumSlots or not C_Container.GetContainerItemInfo then
        return counts, ids, ""
    end
    for bag = 0, 4 do
        local slots = ns.Num(C_Container.GetContainerNumSlots(bag)) or 0
        for slot = 1, slots do
            local ok, info = pcall(C_Container.GetContainerItemInfo, bag, slot)
            if ok and type(info) == "table" then
                local itemId = ns.Num(info.itemID)
                local count = ns.Num(info.stackCount) or 1
                if itemId then
                    if not counts[itemId] then
                        ids[#ids + 1] = itemId
                        counts[itemId] = 0
                    end
                    counts[itemId] = counts[itemId] + count
                end
            end
        end
    end
    table.sort(ids)
    local parts = {}
    for i = 1, #ids do
        local itemId = ids[i]
        parts[#parts + 1] = tostring(itemId) .. ":" .. tostring(counts[itemId])
    end
    return counts, ids, table.concat(parts, ",")
end

function ns.EmitBags(force)
    if not ns.Enabled("bags") then
        return
    end
    local counts, _, text = readBags()
    if not force and text == lastBag then
        return
    end
    if force or not bagCounts then
        bagCounts = counts
        lastBag = text
        ns.bagsReady = true
        ns.Emit("bags", "bags", text)
        return
    end
    local parts = {}
    local seen = {}
    for itemId, count in pairs(counts) do
        seen[itemId] = true
        local delta = count - (bagCounts[itemId] or 0)
        if delta ~= 0 then
            if delta > 0 then
                parts[#parts + 1] = tostring(itemId) .. ":+" .. tostring(delta)
            else
                parts[#parts + 1] = tostring(itemId) .. ":" .. tostring(delta)
            end
        end
    end
    for itemId, previous in pairs(bagCounts) do
        if not seen[itemId] and previous ~= 0 then
            parts[#parts + 1] = tostring(itemId) .. ":-" .. tostring(previous)
        end
    end
    table.sort(parts)
    bagCounts = counts
    lastBag = text
    if #parts > 0 then
        ns.Emit("bag_delta", "bags", table.concat(parts, ","))
    end
end

local function bagSnapshot()
    if not ns.Enabled("bags") or not C_Container then
        return
    end
    if not C_Container.GetContainerNumSlots or not C_Container.GetContainerItemInfo then
        return
    end
    if not ns.bagsReady then
        return
    end
    ns.EmitBags(false)
end

local function factionRows()
    if not C_Reputation or not C_Reputation.GetNumFactions or not C_Reputation.GetFactionDataByIndex then
        return
    end
    local count = ns.Num(C_Reputation.GetNumFactions()) or 0
    for index = 1, count do
        local ok, data = pcall(C_Reputation.GetFactionDataByIndex, index)
        if ok and type(data) == "table" and ns.Flag(data.isHeader) == false then
            local name = ns.Str(data.name)
            local reaction = ns.Num(data.reaction)
            local standing = ns.Num(data.currentStanding)
            if name and name ~= "" and standing then
                local previous = repCache[name]
                local state = tostring(reaction or "") .. ":" .. tostring(standing)
                if repSeeded and previous ~= state then
                    ns.Emit("rep", "rep", name, reaction or "", standing)
                end
                repCache[name] = state
            end
        end
    end
    repSeeded = true
end

local function groupSize()
    local inGroup = IsInGroup and ns.Flag(IsInGroup())
    if inGroup == nil then
        return 1
    end
    if not inGroup then
        return 1
    end
    return ns.Num(GetNumGroupMembers()) or 1
end

function ns.InitWorld()
    ns.Register("CHAT_MSG_LOOT", function(_, message)
        local text = ns.Str(message)
        if text and text ~= "" then
            local itemId, count, quality = ns.ParseLoot(text)
            ns.Emit("loot", "loot", text, itemId, count, quality)
        end
    end)

    ns.Register("CHAT_MSG_SKILL", function(_, message)
        local text = ns.Str(message)
        if text and text ~= "" then
            ns.Emit("skill", "skills", text)
        end
    end)

    ns.Register("UPDATE_FACTION", function()
        if ns.sessionOpen then
            factionRows()
        end
    end)

    ns.Register("BAG_UPDATE_DELAYED", function()
        if ns.sessionOpen then
            bagSnapshot()
        end
    end)

    ns.Register("GROUP_ROSTER_UPDATE", function()
        if not ns.sessionOpen then
            return
        end
        local size = groupSize()
        if size == ns.lastGroup then
            return
        end
        ns.lastGroup = size
        ns.Emit("group", "group", size)
    end)

    ns.Register("PLAYER_DEAD", function()
        local zone, _, map, x, y = ns.Where()
        local summary = {}
        if ns.DeathSummary then
            summary = ns.DeathSummary() or {}
        end
        ns.Emit(
            "death",
            "deaths",
            zone,
            map,
            x,
            y,
            ns.lastLevel or 0,
            summary.name or "",
            summary.id or "",
            summary.level or "",
            summary.ability or "",
            summary.attackers or 0,
            summary.damage or 0
        )
    end)

    ns.Register("PLAYER_UNGHOST", function()
        local zone, _, map, x, y = ns.Where()
        ns.Emit("unghost", "deaths", zone, map, x, y)
    end)

    ns.Register("PLAYER_ALIVE", function()
        local zone, _, map, x, y = ns.Where()
        ns.Emit("alive", "deaths", zone, map, x, y)
    end)

    ns.Register("UNIT_SPELLCAST_SUCCEEDED", function(_, unit, _, spellId)
        if unit ~= "player" then
            return
        end
        spellId = ns.Num(spellId)
        if not spellId then
            return
        end
        local name = ""
        if C_Spell and C_Spell.GetSpellInfo then
            local ok, info = pcall(C_Spell.GetSpellInfo, spellId)
            if ok and type(info) == "table" then
                name = ns.Str(info.name) or ""
            end
        end
        local lowered = string.lower(name)
        if spellId == 8690 or string.find(lowered, "hearth", 1, true) then
            local zone = ns.Str(GetZoneText()) or ""
            ns.travelHint = { method = "hearth", origin = zone, at = GetTime() }
            ns.Emit("travel", "travel", "hearth", zone, "")
        end
    end)

    local function flagState(reader)
        if type(reader) ~= "function" then
            return 0
        end
        local ok, value = pcall(reader, "player")
        if ok and ns.Flag(value) == true then
            return 1
        end
        return 0
    end

    function ns.EmitActivityBaseline()
        local resting = 0
        if type(IsResting) == "function" then
            local ok, value = pcall(IsResting)
            if ok and ns.Flag(value) == true then
                resting = 1
            end
        end
        ns.lastRest = resting
        ns.Emit("rest", "activity", resting)

        local afk = 0
        if type(UnitIsAFK) == "function" then
            afk = flagState(UnitIsAFK)
        end
        ns.lastAfk = afk
        ns.Emit("afk", "activity", afk)

        local mounted = 0
        if type(IsMounted) == "function" then
            local ok, value = pcall(IsMounted)
            if ok and ns.Flag(value) == true then
                mounted = 1
            end
        end
        ns.lastMounted = mounted
        ns.Emit("mount", "activity", mounted)
    end

    ns.Register("PLAYER_UPDATE_RESTING", function()
        if not ns.sessionOpen or not ns.sessionStarted then
            return
        end
        local resting = 0
        if type(IsResting) == "function" then
            local ok, value = pcall(IsResting)
            if ok and ns.Flag(value) == true then
                resting = 1
            end
        end
        if resting == ns.lastRest then
            return
        end
        ns.lastRest = resting
        ns.Emit("rest", "activity", resting)
    end)

    ns.Register("PLAYER_FLAGS_CHANGED", function(_, unit)
        if not ns.sessionOpen or not ns.sessionStarted then
            return
        end
        local unitName = ns.Str(unit)
        if unitName and unitName ~= "player" then
            return
        end
        local afk = 0
        if type(UnitIsAFK) == "function" then
            afk = flagState(UnitIsAFK)
        end
        if afk == ns.lastAfk then
            return
        end
        ns.lastAfk = afk
        ns.Emit("afk", "activity", afk)
    end)

    ns.Register("PLAYER_ENTERING_WORLD", function()
        ns.After(1, function()
            if not ns.sessionOpen then
                return
            end
            factionRows()
            ns.EmitBags(true)
            local size = groupSize()
            if size ~= ns.lastGroup then
                ns.lastGroup = size
                ns.Emit("group", "group", size)
            end
        end)
    end)
end
