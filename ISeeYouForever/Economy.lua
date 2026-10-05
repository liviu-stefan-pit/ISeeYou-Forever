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
            if name == "flight" then
                local zone = ns.Str(GetZoneText()) or ""
                ns.travelHint = { method = "taxi", origin = zone, at = GetTime() }
                ns.Emit("travel", "travel", "taxi", zone, "")
            end
            clearContext(name)
        end)
    end

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
