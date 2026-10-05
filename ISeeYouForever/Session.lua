local addonName, ns = ...

function ns.InitSession()
    ns.Register("PLAYER_ENTERING_WORLD", function()
        if ns.sessionOpen then
            return
        end
        ns.sessionOpen = true

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

        local zone, sub, map, x, y = ns.Where()
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
            ns.RealmName()
        )
        ns.Print(string.format(
            "Recording %s from level %d. Type /isy to choose what is tracked.",
            ns.PlayerName(),
            level
        ))
        pcall(RequestTimePlayed)
    end)

    ns.Register("PLAYER_LOGOUT", function()
        if not ns.sessionOpen or not ISYF_Char.session then
            return
        end
        local session = ISYF_Char.session
        local duration = time() - (session.start or time())
        ns.Emit(
            "session_end",
            nil,
            ns.Num(UnitLevel("player")) or session.level or 0,
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
