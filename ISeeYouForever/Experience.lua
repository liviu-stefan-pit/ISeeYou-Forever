local addonName, ns = ...

function ns.NoteQuestXP(amount, questId)
    amount = tonumber(amount) or 0
    if amount <= 0 then
        return
    end
    ns.pendingQuestXP = {
        amount = amount,
        questId = questId or 0,
        at = GetTime(),
    }
end

function ns.NoteLevel(level)
    level = tonumber(level)
    if not level or not ns.lastLevel or level <= ns.lastLevel then
        return
    end
    ns.lastLevel = level
    ns.Emit("level", "xp", level)
end

function ns.InitExperience()
    ns.Register("PLAYER_LEVEL_UP", function(_, newLevel)
        ns.NoteLevel(ns.Num(newLevel))
    end)

    ns.Register("PLAYER_XP_UPDATE", function()
        ns.After(0.1, function()
            if not ns.sessionOpen then
                return
            end
            local xp = ns.Num(UnitXP("player"))
            local xpMax = ns.Num(UnitXPMax("player")) or ns.lastXPMax or 0
            local level = ns.Num(UnitLevel("player")) or ns.lastLevel or 0
            if not xp or ns.lastXP == nil then
                ns.lastXP = xp
                ns.lastXPMax = xpMax
                return
            end

            local gain = xp - ns.lastXP
            if gain < 0 then
                gain = ((ns.lastXPMax or 0) - ns.lastXP) + xp
            end
            ns.lastXP = xp
            ns.lastXPMax = xpMax
            ns.NoteLevel(level)
            if gain <= 0 then
                return
            end

            local restedLeft = 0
            local exhaust = ns.Num(GetXPExhaustion()) or 0
            if ns.lastExhaust and exhaust < ns.lastExhaust then
                restedLeft = ns.lastExhaust - exhaust
                if restedLeft > gain then
                    restedLeft = gain
                end
            end
            ns.lastExhaust = exhaust

            local questGain = 0
            local questId = ""
            local pending = ns.pendingQuestXP
            if pending and (GetTime() - (pending.at or 0)) >= 2 then
                ns.pendingQuestXP = nil
                pending = nil
            end
            if pending and pending.amount > 0 and gain >= pending.amount then
                questGain = pending.amount
                questId = pending.questId or ""
                ns.pendingQuestXP = nil
            end

            local function takeRested(amount)
                local used = restedLeft
                if used > amount then
                    used = amount
                end
                restedLeft = restedLeft - used
                return used
            end

            if questGain > 0 then
                ns.Emit("xp", "xp", questGain, takeRested(questGain), level, "quest", "", "", "", "", questId)
            end

            local otherGain = gain - questGain
            if otherGain <= 0 then
                return
            end
            local source = "other"
            local mobName, mobLevel, mobClass, mobType = "", "", "", ""
            if ns.fight then
                source = "kill"
                local mob = ns.fight.mob
                if not mob and ns.LastMob then
                    mob = ns.LastMob()
                end
                if mob then
                    mobName = mob.name or ""
                    mobLevel = mob.level or ""
                    mobClass = mob.class or ""
                    mobType = mob.creatureType or ""
                    ns.NoteFightXP(otherGain, mob)
                else
                    ns.NoteFightXP(otherGain, nil)
                end
            end
            ns.Emit("xp", "xp", otherGain, takeRested(otherGain), level, source, mobName, mobLevel, mobClass, mobType, "")
        end)
    end)
end
