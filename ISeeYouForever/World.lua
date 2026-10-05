local addonName, ns = ...

local repSeeded = false
local repCache = {}
local lastBag = ""
local lastBagAt = 0

local function bagSnapshot()
    if not ns.Enabled("bags") or not C_Container then
        return
    end
    if not C_Container.GetContainerNumSlots or not C_Container.GetContainerItemInfo then
        return
    end
    local counts = {}
    local ids = {}
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
    local text = table.concat(parts, ",")
    local now = time()
    if text == lastBag and (now - lastBagAt) < 20 then
        return
    end
    if text == lastBag then
        return
    end
    lastBag = text
    lastBagAt = now
    ns.Emit("bags", "bags", text)
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
            ns.Emit("loot", "loot", text)
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
        ns.Emit("death", "deaths", zone, map, x, y, ns.lastLevel or 0)
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

    ns.Register("PLAYER_ENTERING_WORLD", function()
        ns.After(1, function()
            if not ns.sessionOpen then
                return
            end
            factionRows()
            bagSnapshot()
            local size = groupSize()
            if size ~= ns.lastGroup then
                ns.lastGroup = size
                ns.Emit("group", "group", size)
            end
        end)
    end)
end
