local addonName, ns = ...

function ns.NoteQuestMoney(copper, questId)
    copper = tonumber(copper) or 0
    if copper == 0 then
        return
    end
    ns.pendingQuestMoney = {
        copper = copper,
        questId = questId or 0,
        at = GetTime(),
    }
end

local function setContext(name)
    ns.moneyContext = name
end

local function clearContext(name)
    if ns.moneyContext == name then
        ns.moneyContext = nil
    end
end

local function resolveMoney(delta)
    local now = GetTime()
    if ns.repairUntil and now < ns.repairUntil then
        ns.repairUntil = nil
        return "repair", ""
    end
    local pending = ns.pendingQuestMoney
    if pending and (now - (pending.at or 0)) < 2 and pending.copper == delta then
        ns.pendingQuestMoney = nil
        return "quest", tostring(pending.questId or "")
    end
    if ns.lootMoneyAt and (now - ns.lootMoneyAt) < 1 then
        ns.lootMoneyAt = nil
        return "loot", ""
    end
    if ns.moneyContext then
        return ns.moneyContext, ""
    end
    return "unknown", ""
end

function ns.InitEconomy()
    local windows = {
        { "MERCHANT_SHOW", "MERCHANT_CLOSED", "vendor" },
        { "TRAINER_SHOW", "TRAINER_CLOSED", "trainer" },
        { "TAXIMAP_OPENED", "TAXIMAP_CLOSED", "flight" },
        { "MAIL_SHOW", "MAIL_CLOSED", "mail" },
        { "AUCTION_HOUSE_SHOW", "AUCTION_HOUSE_CLOSED", "auction" },
        { "TRADE_SHOW", "TRADE_CLOSED", "trade" },
    }
    for i = 1, #windows do
        local openEvent, closeEvent, name = windows[i][1], windows[i][2], windows[i][3]
        ns.Register(openEvent, function()
            setContext(name)
        end)
        ns.Register(closeEvent, function()
            clearContext(name)
        end)
    end

    if type(hooksecurefunc) == "function" and type(RepairAllItems) == "function" then
        hooksecurefunc("RepairAllItems", function()
            ns.repairUntil = GetTime() + 2
        end)
    end

    if type(hooksecurefunc) == "function" and type(TakeTaxiNode) == "function" then
        hooksecurefunc("TakeTaxiNode", function(index)
            if not ns.sessionOpen then
                return
            end
            index = tonumber(index)
            local dest = ""
            if index and type(TaxiNodeName) == "function" then
                local ok, name = pcall(TaxiNodeName, index)
                if ok then
                    dest = ns.Str(name) or ""
                end
            end
            local zone = ns.Str(GetZoneText()) or ""
            ns.taxiDest = dest
            ns.taxiOrigin = zone
            ns.onTaxi = true
            ns.travelHint = { method = "taxi", origin = zone, at = GetTime() }
            ns.Emit("taxi_start", "travel", zone, dest)
        end)
    end

    local taxiWaits = 0
    local function finishTaxi()
        if not ns.onTaxi then
            taxiWaits = 0
            return
        end
        if type(UnitOnTaxi) == "function" then
            local ok, onTaxi = pcall(UnitOnTaxi, "player")
            if ok and ns.Flag(onTaxi) == true and taxiWaits < 10 then
                taxiWaits = taxiWaits + 1
                ns.After(0.5, finishTaxi)
                return
            end
        end
        taxiWaits = 0
        ns.onTaxi = false
        local zone, _, map, x, y = ns.Where()
        ns.Emit("taxi_end", "travel", ns.taxiDest or "", zone, map, x, y)
        ns.taxiDest = nil
    end

    ns.Register("PLAYER_CONTROL_GAINED", function()
        if ns.onTaxi then
            ns.After(0.2, finishTaxi)
        end
    end)

    ns.Register("CHAT_MSG_MONEY", function()
        ns.lootMoneyAt = GetTime()
    end)

    ns.Register("PLAYER_MONEY", function()
        local balance = ns.Num(GetMoney())
        if not balance then
            return
        end
        if ns.lastMoney == nil then
            ns.lastMoney = balance
            return
        end
        local delta = balance - ns.lastMoney
        ns.lastMoney = balance
        if delta == 0 then
            return
        end
        ns.After(0.1, function()
            local source, detail = resolveMoney(delta)
            ns.Emit("money", "money", delta, balance, source, detail)
        end)
    end)
end
