local addonName, ns = ...

local function snapshotTarget()
    if not ns.Enabled("mobs") then
        return nil
    end
    local exists = UnitExists("target")
    if ns.Flag(exists) ~= true then
        return nil
    end
    local player = UnitIsPlayer("target")
    if ns.Flag(player) ~= false then
        return nil
    end
    local name = ns.Str(UnitName("target"))
    if not name or name == "" then
        return nil
    end
    return {
        name = name,
        level = ns.Num(UnitLevel("target")) or "",
        class = ns.Str(UnitClassification("target")) or "",
        creatureType = ns.Str(UnitCreatureType("target")) or "",
    }
end

function ns.LastMob()
    if not ns.lastMob then
        return nil
    end
    if (GetTime() - (ns.lastMobAt or 0)) > 15 then
        return nil
    end
    return ns.lastMob
end

function ns.NoteFightXP(amount, mob)
    if not ns.fight then
        return
    end
    ns.fight.xp = (ns.fight.xp or 0) + (tonumber(amount) or 0)
    ns.fight.ticks = (ns.fight.ticks or 0) + 1
    if mob and mob.name and mob.name ~= "" then
        ns.fight.named = (ns.fight.named or 0) + 1
        ns.fight.mob = mob
    end
end

local function rememberMob(mob, context)
    if not mob then
        return
    end
    ns.lastMob = mob
    ns.lastMobAt = GetTime()
    local zone, _, map, x, y = ns.Where()
    ns.Emit("mob", "mobs", mob.name, mob.level, mob.class, mob.creatureType, zone, map, x, y, context)
end

function ns.InitEngagements()
    ns.Register("PLAYER_TARGET_CHANGED", function()
        local mob = snapshotTarget()
        if not mob then
            return
        end
        if ns.lastMob and ns.lastMob.name == mob.name and (GetTime() - (ns.lastMobAt or 0)) < 2 then
            ns.lastMob = mob
            ns.lastMobAt = GetTime()
            return
        end
        rememberMob(mob, "target")
    end)

    ns.Register("PLAYER_REGEN_DISABLED", function()
        local mob = snapshotTarget() or ns.LastMob()
        if mob then
            ns.lastMob = mob
            ns.lastMobAt = GetTime()
        end
        local zone, _, map, x, y = ns.Where()
        ns.fight = {
            start = GetTime(),
            xp = 0,
            ticks = 0,
            named = 0,
            mob = mob,
            zone = zone,
            map = map,
            x = x,
            y = y,
        }
        ns.Emit(
            "fight_start",
            "fights",
            zone,
            map,
            x,
            y,
            mob and mob.name or "",
            mob and mob.level or "",
            mob and mob.class or "",
            mob and mob.creatureType or ""
        )
    end)

    ns.Register("PLAYER_REGEN_ENABLED", function()
        local fight = ns.fight
        if not fight or fight.closing then
            return
        end
        fight.closing = true
        fight.ending = GetTime()
        ns.After(0.2, function()
            if ns.fight == fight then
                ns.fight = nil
            end
            local duration = (fight.ending or GetTime()) - (fight.start or GetTime())
            if duration < 0 then
                duration = 0
            end
            local zone, _, map, x, y = ns.Where()
            ns.Emit(
                "fight_end",
                "fights",
                string.format("%.1f", duration),
                fight.xp or 0,
                zone,
                map,
                x,
                y,
                fight.named or 0,
                fight.ticks or 0
            )
        end)
    end)
end
