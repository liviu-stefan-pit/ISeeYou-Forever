local addonName, ns = ...

ns.ADDON = addonName

ns.SCHEMA = 3

ns.CATEGORIES = {
    { key = "xp", label = "Experience and level-ups" },
    { key = "quests", label = "Quests" },
    { key = "money", label = "Money" },
    { key = "routes", label = "Routes (map position samples)" },
    { key = "travel", label = "Zones and travel" },
    { key = "fights", label = "Fights (engagement duration and XP inside the window)" },
    { key = "mobs", label = "Mob identity (name, level, classification, creature type)" },
    { key = "deaths", label = "Deaths" },
    { key = "loot", label = "Loot" },
    { key = "skills", label = "Skills" },
    { key = "rep", label = "Reputation" },
    { key = "bags", label = "Bags" },
    { key = "group", label = "Group size" },
    { key = "character", label = "Character, talents, and gear" },
    { key = "npcs", label = "NPCs (vendors, trainers, quest givers)" },
    { key = "activity", label = "Activity (rest, afk, mount, taxi)" },
}

function ns.IsSecret(value)
    return type(issecretvalue) == "function" and issecretvalue(value) or false
end

function ns.Num(value)
    if ns.IsSecret(value) then
        return nil
    end
    if type(value) ~= "number" then
        return nil
    end
    return value
end

function ns.Str(value)
    if ns.IsSecret(value) then
        return nil
    end
    if type(value) ~= "string" then
        return nil
    end
    return value
end

function ns.Flag(value)
    if ns.IsSecret(value) then
        return nil
    end
    if value == true or value == 1 then
        return true
    end
    if value == false or value == nil then
        return false
    end
    return value and true or false
end

function ns.Field(value)
    if value == nil or ns.IsSecret(value) then
        return ""
    end
    local text = tostring(value)
    text = text:gsub("[\t\r\n]", " ")
    if #text > 400 then
        text = text:sub(1, 400)
    end
    return text
end

function ns.PlayerName()
    local name = ns.Str(UnitName("player"))
    if name and name ~= "" then
        return name
    end
    return "this character"
end

function ns.RealmName()
    return ns.Str(GetRealmName()) or ""
end

function ns.MapPoint()
    if not C_Map or not C_Map.GetBestMapForUnit or not C_Map.GetPlayerMapPosition then
        return 0, 0, 0
    end
    local map = ns.Num(C_Map.GetBestMapForUnit("player"))
    if not map then
        return 0, 0, 0
    end
    local ok, pos = pcall(C_Map.GetPlayerMapPosition, map, "player")
    if not ok or not pos or ns.IsSecret(pos) or not pos.GetXY then
        return map, 0, 0
    end
    local xOk, x, y = pcall(pos.GetXY, pos)
    if not xOk then
        return map, 0, 0
    end
    x, y = ns.Num(x), ns.Num(y)
    if not x or not y then
        return map, 0, 0
    end
    return map, math.floor(x * 10000 + 0.5), math.floor(y * 10000 + 0.5)
end

function ns.NpcIdFromGuid(guid)
    local text = ns.Str(guid)
    if not text or text == "" then
        return ""
    end
    local npcId = string.match(text, "^[Cc]reature%-%d+%-%d+%-%d+%-%d+%-(%d+)")
    if not npcId then
        npcId = string.match(text, "^[Vv]ehicle%-%d+%-%d+%-%d+%-%d+%-(%d+)")
    end
    return npcId or ""
end

function ns.UnitNpc(unit)
    if not unit or type(UnitExists) ~= "function" then
        return "", ""
    end
    local ok, exists = pcall(UnitExists, unit)
    if not ok or ns.Flag(exists) ~= true then
        return "", ""
    end
    local name = ns.Str(UnitName(unit)) or ""
    local guid = ""
    if type(UnitGUID) == "function" then
        local guidOk, value = pcall(UnitGUID, unit)
        if guidOk then
            guid = ns.Str(value) or ""
        end
    end
    return name, ns.NpcIdFromGuid(guid)
end

function ns.InteractNpc()
    local name, npcId = ns.UnitNpc("npc")
    if name ~= "" or npcId ~= "" then
        return name, npcId
    end
    return ns.UnitNpc("questnpc")
end

function ns.ItemIdFromLink(link)
    local text = ns.Str(link) or tostring(link or "")
    if ns.IsSecret(link) then
        return ""
    end
    local itemId = string.match(text, "item:(%d+)")
    return itemId or ""
end

function ns.ParseLoot(message)
    local text = ns.Str(message) or ""
    local itemId = string.match(text, "item:(%d+)") or ""
    local count = string.match(text, "x(%d+)") or ""
    if count == "" and itemId ~= "" then
        count = "1"
    end
    local quality = string.match(text, "|cnIQ(%d+):") or ""
    if quality == "" then
        local hex = string.match(text, "|c(%x%x%x%x%x%x%x%x)")
        local colors = {
            ff9d9d9d = "0",
            ffffffff = "1",
            ff1eff00 = "2",
            ff0070dd = "3",
            ffa335ee = "4",
            ffff8000 = "5",
            ffe6cc80 = "6",
            ff00ccff = "7",
        }
        if hex then
            quality = colors[string.lower(hex)] or ""
        end
    end
    return itemId, count, quality
end

function ns.Where()
    local zone = ns.Str(GetZoneText()) or ""
    local sub = ns.Str(GetSubZoneText()) or ""
    local map, x, y = ns.MapPoint()
    return zone, sub, map, x, y
end

function ns.FormatDuration(seconds)
    seconds = tonumber(seconds) or 0
    if seconds < 0 then
        seconds = 0
    end
    local hours = math.floor(seconds / 3600)
    local minutes = math.floor((seconds % 3600) / 60)
    local secs = math.floor(seconds % 60)
    if hours > 0 then
        return string.format("%dh %dm", hours, minutes)
    end
    return string.format("%dm %ds", minutes, secs)
end

function ns.FormatCopper(copper)
    copper = tonumber(copper) or 0
    local negative = copper < 0
    if negative then
        copper = -copper
    end
    local gold = math.floor(copper / 10000)
    local silver = math.floor((copper % 10000) / 100)
    local coins = copper % 100
    local text
    if gold > 0 then
        text = string.format("%dg %ds %dc", gold, silver, coins)
    elseif silver > 0 then
        text = string.format("%ds %dc", silver, coins)
    else
        text = string.format("%dc", coins)
    end
    if negative then
        return "-" .. text
    end
    return text
end

function ns.After(seconds, callback)
    if C_Timer and C_Timer.After then
        C_Timer.After(seconds, callback)
    else
        callback()
    end
end

function ns.Print(message)
    print("|cffd4a85a[I see you forever]|r " .. message)
end
