local addonName, ns = ...

function ns.Enabled(key)
    local track = ISYF_Char and ISYF_Char.track
    if not track or track[key] == nil then
        return true
    end
    return track[key] and true or false
end

function ns.SessionId()
    local session = ISYF_Char and ISYF_Char.session
    if session and session.id then
        return session.id
    end
    return 0
end

function ns.NextId()
    local accountId = (ISYF_DB and tonumber(ISYF_DB.nextId)) or 1
    local charId = (ISYF_Char and tonumber(ISYF_Char.nextId)) or 1
    local id = accountId
    if charId > id then
        id = charId
    end
    ISYF_DB.nextId = id + 1
    ISYF_Char.nextId = id + 1
    return id
end

function ns.ApplyStats(kind, fields)
    local session = ISYF_Char.session
    if not session then
        return
    end
    if kind == "xp" then
        local amount = tonumber(fields[1]) or 0
        session.xp = (session.xp or 0) + amount
        local source = fields[4]
        if source == "quest" then
            session.questXp = (session.questXp or 0) + amount
        elseif source == "kill" then
            session.killXp = (session.killXp or 0) + amount
        end
        ns.recentXp = ns.recentXp or {}
        local now = time()
        ns.recentXp[#ns.recentXp + 1] = { t = now, amount = amount }
        local cutoff = now - (15 * 60)
        local kept = {}
        for i = 1, #ns.recentXp do
            if ns.recentXp[i].t >= cutoff then
                kept[#kept + 1] = ns.recentXp[i]
            end
        end
        ns.recentXp = kept
    elseif kind == "money" then
        local delta = tonumber(fields[1]) or 0
        if delta > 0 then
            session.copperIn = (session.copperIn or 0) + delta
        elseif delta < 0 then
            session.copperOut = (session.copperOut or 0) - delta
        end
    end
end

function ns.SessionRates()
    local session = ISYF_Char and ISYF_Char.session
    if not session or not session.start then
        return nil
    end
    local now = time()
    local window = 15 * 60
    local recent = 0
    local oldest = nil
    local gains = ns.recentXp or {}
    for i = 1, #gains do
        local gain = gains[i]
        if gain.t and (now - gain.t) <= window then
            recent = recent + (gain.amount or 0)
            if not oldest or gain.t < oldest then
                oldest = gain.t
            end
        end
    end
    local rate = 0
    if oldest and recent > 0 and now > oldest then
        local span = now - oldest
        if span < 60 then
            span = 60
        end
        rate = recent / span * 3600
    end
    if rate <= 0 then
        local elapsed = now - (session.start or now)
        if elapsed > 0 and (session.xp or 0) > 0 then
            rate = (session.xp or 0) / elapsed * 3600
        end
    end
    local xp = 0
    local xpMax = 0
    if type(UnitXP) == "function" then
        xp = ns.Num(UnitXP("player")) or 0
    end
    if type(UnitXPMax) == "function" then
        xpMax = ns.Num(UnitXPMax("player")) or 0
    end
    local remain = xpMax - xp
    if remain < 0 then
        remain = 0
    end
    local eta = nil
    if rate > 0 and remain > 0 then
        eta = remain / rate * 3600
    end
    local rested = 0
    if type(GetXPExhaustion) == "function" then
        rested = ns.Num(GetXPExhaustion()) or 0
    end
    local questXp = session.questXp or 0
    local killXp = session.killXp or 0
    local split = questXp + killXp
    local level = session.level or 0
    if type(UnitLevel) == "function" then
        level = ns.Num(UnitLevel("player")) or level
    end
    return {
        rate = rate,
        eta = eta,
        rested = rested,
        questPct = split > 0 and math.floor(questXp / split * 100 + 0.5) or 0,
        killPct = split > 0 and math.floor(killXp / split * 100 + 0.5) or 0,
        hasSplit = split > 0,
        nextLevel = (level or 0) + 1,
    }
end

function ns.Emit(kind, category, ...)
    if ns.emitQueue then
        ns.emitQueue[#ns.emitQueue + 1] = {
            kind = kind,
            category = category,
            n = select("#", ...),
            ...,
        }
        return
    end
    if not ISYF_Char or not ISYF_Char.events then
        return
    end
    if category and not ns.Enabled(category) then
        return
    end
    local fields = { ... }
    local parts = {
        tostring(ns.NextId()),
        tostring(time()),
        tostring(ns.SessionId()),
        kind,
    }
    for i = 1, #fields do
        parts[#parts + 1] = ns.Field(fields[i])
    end
    ISYF_Char.events[#ISYF_Char.events + 1] = table.concat(parts, "\t")
    ns.ApplyStats(kind, fields)
    if ns.RefreshStatus then
        ns.RefreshStatus()
    end
    if ns.LogLive then
        ns.LogLive(kind, fields, time())
    end
end

function ns.FlushEmitQueue()
    local queued = ns.emitQueue
    ns.emitQueue = nil
    if not queued then
        return
    end
    for i = 1, #queued do
        local row = queued[i]
        ns.Emit(row.kind, row.category, unpack(row, 1, row.n))
    end
end
