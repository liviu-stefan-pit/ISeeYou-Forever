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
        session.xp = (session.xp or 0) + (tonumber(fields[1]) or 0)
    elseif kind == "money" then
        local delta = tonumber(fields[1]) or 0
        if delta > 0 then
            session.copperIn = (session.copperIn or 0) + delta
        elseif delta < 0 then
            session.copperOut = (session.copperOut or 0) - delta
        end
    end
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
