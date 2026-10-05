local addonName, ns = ...

local seeded = false
local recentTurnIn = {}
local pendingGiver
local pendingTurnin
local pendingReward

local function questTitle(questId)
    if not questId or not C_QuestLog or not C_QuestLog.GetTitleForQuestID then
        return ""
    end
    local ok, title = pcall(C_QuestLog.GetTitleForQuestID, questId)
    if not ok then
        return ""
    end
    return ns.Str(title) or ""
end

local function touchQuest(questId, title)
    local quests = ISYF_Char.quests
    local row = quests[questId]
    if not row then
        row = { progress = {} }
        quests[questId] = row
    end
    if title and title ~= "" then
        row.title = title
    end
    row.progress = row.progress or {}
    return row
end

local function freshNpc(pending, seconds)
    if not pending or not pending.at then
        return "", ""
    end
    if (GetTime() - pending.at) > (seconds or 10) then
        return "", ""
    end
    return pending.name or "", pending.id or ""
end

local function rememberNpc(target)
    local name, npcId = ns.InteractNpc()
    if name == "" and npcId == "" then
        return
    end
    if target == "turnin" then
        pendingTurnin = { name = name, id = npcId, at = GetTime() }
    else
        pendingGiver = { name = name, id = npcId, at = GetTime() }
    end
end

local function logAccept(row, questId, title)
    if row.loggedAccept then
        return
    end
    row.loggedAccept = true
    row.accepted = time()
    local zone, _, map, x, y = ns.Where()
    local giverName, giverId = freshNpc(pendingGiver, 10)
    ns.Emit(
        "quest_accept",
        "quests",
        questId,
        title,
        ns.lastLevel or 0,
        zone,
        map,
        x,
        y,
        giverName,
        giverId
    )
end

local function logSeen(row, questId, title)
    if row.loggedSeen then
        return
    end
    row.loggedSeen = true
    row.preexisting = true
    row.loggedAccept = true
    local zone, _, map, x, y = ns.Where()
    ns.Emit("quest_seen", "quests", questId, title, ns.lastLevel or 0, zone, map, x, y)
end

local function objectivesOf(questId)
    if not C_QuestLog or not C_QuestLog.GetQuestObjectives then
        return nil
    end
    local ok, result = pcall(C_QuestLog.GetQuestObjectives, questId)
    if not ok or type(result) ~= "table" then
        return nil
    end
    return result
end

local function recentlyTurnedIn(questId)
    local turned = recentTurnIn[questId]
    return turned and (GetTime() - turned) < 5
end

local function noteReady(row, questId, title)
    if row.readyLogged then
        return
    end
    row.readyLogged = true
    local zone, _, map, x, y = ns.Where()
    ns.Emit("quest_ready", "quests", questId, row.title or title, ns.lastLevel or 0, zone, map, x, y)
end

local function scanQuestLog()
    if not C_QuestLog or not C_QuestLog.GetNumQuestLogEntries or not C_QuestLog.GetInfo then
        return
    end
    local count = ns.Num(C_QuestLog.GetNumQuestLogEntries()) or 0
    for index = 1, count do
        local ok, info = pcall(C_QuestLog.GetInfo, index)
        if ok and type(info) == "table" then
            local header = ns.Flag(info.isHeader)
            local questId = ns.Num(info.questID)
            if header == false and questId and questId > 0 and not recentlyTurnedIn(questId) then
                local title = ns.Str(info.title) or questTitle(questId)
                local existed = ISYF_Char.quests[questId] ~= nil
                local row = touchQuest(questId, title)
                if not seeded then
                    logSeen(row, questId, title)
                    if ns.Flag(info.isComplete) == true then
                        row.readyLogged = true
                    end
                elseif not existed then
                    logAccept(row, questId, title)
                end
                local objectives = objectivesOf(questId)
                local anyRequired = false
                local allDone = true
                if objectives then
                    for i = 1, #objectives do
                        local objective = objectives[i]
                        if type(objective) == "table" then
                            local text = ns.Str(objective.text) or ""
                            local done = ns.Num(objective.numFulfilled)
                            local required = ns.Num(objective.numRequired)
                            if required and required > 0 then
                                anyRequired = true
                                if not done or done < required then
                                    allDone = false
                                end
                            end
                            local key = tostring(i) .. ":" .. text
                            local state = tostring(done or "") .. "/" .. tostring(required or "")
                            if seeded and row.progress[key] ~= nil and row.progress[key] ~= state then
                                local zone, _, map, x, y = ns.Where()
                                ns.Emit(
                                    "quest_progress",
                                    "quests",
                                    questId,
                                    row.title or title,
                                    text,
                                    done or "",
                                    required or "",
                                    ns.lastLevel or 0,
                                    zone,
                                    map,
                                    x,
                                    y
                                )
                            end
                            row.progress[key] = state
                        end
                    end
                end
                local complete = ns.Flag(info.isComplete) == true or (anyRequired and allDone)
                if seeded and complete then
                    noteReady(row, questId, title)
                elseif complete then
                    row.readyLogged = true
                end
            end
        end
    end
    seeded = true
end

function ns.InitQuests()
    local scanQueued = false
    ns.Register("QUEST_LOG_UPDATE", function()
        if not ns.sessionOpen or scanQueued then
            return
        end
        scanQueued = true
        ns.After(0.2, function()
            scanQueued = false
            if ns.sessionOpen then
                scanQuestLog()
            end
        end)
    end)

    ns.Register("QUEST_DETAIL", function()
        rememberNpc("giver")
    end)

    ns.Register("QUEST_PROGRESS", function()
        rememberNpc("turnin")
    end)

    ns.Register("QUEST_COMPLETE", function()
        rememberNpc("turnin")
    end)

    if type(hooksecurefunc) == "function" and type(GetQuestReward) == "function" then
        hooksecurefunc("GetQuestReward", function(choice)
            choice = tonumber(choice)
            if not choice or type(GetQuestItemLink) ~= "function" then
                return
            end
            local ok, link = pcall(GetQuestItemLink, "choice", choice)
            local itemId = ""
            if ok then
                itemId = ns.ItemIdFromLink(link)
            end
            pendingReward = { item = itemId, at = GetTime() }
        end)
    end

    ns.Register("QUEST_ACCEPTED", function(_, questId)
        questId = ns.Num(questId)
        if not questId or recentlyTurnedIn(questId) then
            return
        end
        local title = questTitle(questId)
        local row = touchQuest(questId, title)
        logAccept(row, questId, title)
        seeded = true
    end)

    ns.Register("QUEST_TURNED_IN", function(_, questId, xpReward, moneyReward)
        questId = ns.Num(questId)
        if not questId then
            return
        end
        local xp = ns.Num(xpReward) or 0
        local copper = ns.Num(moneyReward) or 0
        local row = ISYF_Char.quests[questId]
        local title = (row and row.title) or questTitle(questId)
        local accepted = row and row.accepted or ""
        local duration = ""
        if row and row.accepted then
            duration = time() - row.accepted
        end
        recentTurnIn[questId] = GetTime()
        ns.NoteQuestXP(xp, questId)
        if ns.NoteQuestMoney then
            ns.NoteQuestMoney(copper, questId)
        end
        local zone, _, map, x, y = ns.Where()
        local npcName, npcId = freshNpc(pendingTurnin, 10)
        local reward = ""
        if pendingReward and (GetTime() - (pendingReward.at or 0)) < 5 then
            reward = pendingReward.item or ""
        end
        pendingReward = nil
        ns.Emit(
            "quest_turnin",
            "quests",
            questId,
            title,
            xp,
            copper,
            ns.lastLevel or 0,
            zone,
            map,
            x,
            y,
            accepted,
            duration,
            npcName,
            npcId,
            reward
        )
        ISYF_Char.quests[questId] = nil
    end)

    ns.Register("QUEST_REMOVED", function(_, questId)
        questId = ns.Num(questId)
        if not questId then
            return
        end
        local turned = recentTurnIn[questId]
        recentTurnIn[questId] = nil
        if turned and (GetTime() - turned) < 2 then
            return
        end
        local row = ISYF_Char.quests[questId]
        local title = (row and row.title) or questTitle(questId)
        ns.Emit("quest_abandon", "quests", questId, title, ns.lastLevel or 0)
        ISYF_Char.quests[questId] = nil
    end)
end
