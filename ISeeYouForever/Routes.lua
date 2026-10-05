local addonName, ns = ...

local sampler
local lastMap, lastX, lastY, lastAt
local lastZoneKey = ""

local function sampleRoute(force)
    if not ns.Enabled("routes") or not ns.sessionOpen then
        return
    end
    local map, x, y = ns.MapPoint()
    if map == 0 or (x == 0 and y == 0) then
        return
    end
    local now = time()
    local moved = lastMap ~= map or not lastX or math.abs(x - lastX) >= 20 or math.abs(y - lastY) >= 20
    local drifted = lastMap ~= map or x ~= lastX or y ~= lastY
    local due = (now - (lastAt or 0)) >= 3
    if not force and not moved and not (due and drifted) then
        return
    end
    lastMap, lastX, lastY, lastAt = map, x, y, now
    local zone = ns.Str(GetZoneText()) or ""
    ns.Emit("route", "routes", map, x, y, zone)
end

function ns.SyncRouteSampler()
    if not sampler then
        return
    end
    if ns.Enabled("routes") then
        sampler:Show()
    else
        sampler:Hide()
    end
end

function ns.InitRoutes()
    sampler = CreateFrame("Frame")
    local wait = 0
    sampler:SetScript("OnUpdate", function(_, elapsed)
        wait = wait + elapsed
        if wait < 2 then
            return
        end
        wait = 0
        sampleRoute(false)
    end)
    ns.SyncRouteSampler()

    local function onZone()
        if not ns.sessionOpen then
            return
        end
        local zone, sub, map, x, y = ns.Where()
        local key = zone .. "/" .. sub
        if key == lastZoneKey then
            return
        end
        lastZoneKey = key
        ns.Emit("zone", "travel", zone, sub, map, x, y)
        local hint = ns.travelHint
        if hint and (GetTime() - (hint.at or 0)) < 120 then
            ns.Emit("travel", "travel", hint.method or "zone", hint.origin or "", zone)
            ns.travelHint = nil
        end
        sampleRoute(true)
    end

    ns.Register("ZONE_CHANGED_NEW_AREA", onZone)
    ns.Register("ZONE_CHANGED", onZone)
    ns.Register("ZONE_CHANGED_INDOORS", onZone)
end
