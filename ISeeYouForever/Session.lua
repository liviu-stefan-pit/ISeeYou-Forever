local addonName, ns = ...

function ns.InitSession()
    ns.Register("PLAYER_ENTERING_WORLD", function()
        if ns.sessionOpen then
            return
        end
        ns.sessionOpen = true
        ns.sessionStarted = false
        ns.emitQueue = {}

        local level = ns.Num(UnitLevel("player")) or 0
        local xp = ns.Num(UnitXP("player")) or 0
        local xpMax = ns.Num(UnitXPMax("player")) or 0
        local money = ns.Num(GetMoney()) or 0
        local exhaust = ns.Num(GetXPExhaustion()) or 0

        ns.lastXP = xp
        ns.lastXPMax = xpMax
        ns.lastLevel = level
        ns.lastMoney = money
        ns.lastExhaust = exhaust

        local sessionId = (tonumber(ISYF_Char.sessionCount) or 0) + 1
        ISYF_Char.sessionCount = sessionId
        ISYF_Char.session = {
            id = sessionId,
            start = time(),
            xp = 0,
            copperIn = 0,
            copperOut = 0,
            level = level,
        }
        if not ISYF_Char.baseline then
            ISYF_Char.baseline = {
                level = level,
                xp = xp,
                money = money,
                started = time(),
            }
        end
        if ns.CaptureGear then
            ns.CaptureGear()
        end

        local function emitStart()
            if ns.sessionStarted then
                return
            end
            ns.sessionStarted = true
            local zone, sub, map, x, y = ns.Where()
            local queued = ns.emitQueue
            ns.emitQueue = nil
            ns.Emit(
                "session_start",
                nil,
                level,
                zone,
                sub,
                map,
                x,
                y,
                money,
                xp,
                xpMax,
                ns.PlayerName(),
                ns.RealmName(),
                ns.SCHEMA or 2
            )
            if ns.EmitCharacter then
                ns.EmitCharacter("login")
            end
            if ns.EmitActivityBaseline then
                ns.EmitActivityBaseline()
            end
            if queued then
                for i = 1, #queued do
                    local row = queued[i]
                    ns.Emit(row.kind, row.category, unpack(row, 1, row.n))
                end
            end
            ns.Print(string.format(
                "Recording %s from level %d. Type /isy to choose what is tracked.",
                ns.PlayerName(),
                level
            ))
            pcall(RequestTimePlayed)
        end

        local function tryStart(attempt)
            if ns.sessionStarted then
                return
            end
            local zone = ns.Str(GetZoneText())
            if (not zone or zone == "") and attempt < 8 then
                ns.After(0.5, function()
                    tryStart(attempt + 1)
                end)
                return
            end
            emitStart()
        end

        ns.ForceSessionStart = emitStart
        tryStart(0)
    end)

    ns.Register("PLAYER_LOGOUT", function()
        if not ns.sessionOpen or not ISYF_Char.session then
            return
        end
        if not ns.sessionStarted and ns.ForceSessionStart then
            ns.ForceSessionStart()
        end
        local session = ISYF_Char.session
        local duration = time() - (session.start or time())
        local level = ns.Num(UnitLevel("player")) or 0
        local tracked = tonumber(ns.lastLevel) or 0
        if tracked > level then
            level = tracked
        end
        if ns.EmitBags then
            ns.EmitBags(true)
        end
        ns.Emit(
            "session_end",
            nil,
            level,
            duration,
            session.xp or 0,
            session.copperIn or 0,
            session.copperOut or 0
        )
        ns.sessionOpen = false
    end)

    ns.Register("TIME_PLAYED_MSG", function(_, totalTime, levelTime)
        totalTime = ns.Num(totalTime) or 0
        levelTime = ns.Num(levelTime) or 0
        ns.Emit("played", nil, totalTime, levelTime)
    end)
end
