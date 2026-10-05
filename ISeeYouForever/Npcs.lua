local addonName, ns = ...

local openedAt = {}

local WINDOWS = {
    { "MERCHANT_SHOW", "MERCHANT_CLOSED", "vendor" },
    { "TRAINER_SHOW", "TRAINER_CLOSED", "trainer" },
    { "GOSSIP_SHOW", "GOSSIP_CLOSED", "gossip" },
    { "TAXIMAP_OPENED", "TAXIMAP_CLOSED", "flight" },
    { "BANKFRAME_OPENED", "BANKFRAME_CLOSED", "bank" },
    { "QUEST_DETAIL", "QUEST_FINISHED", "quest" },
}

local function spellName(spellId)
    if not spellId then
        return ""
    end
    if C_Spell and C_Spell.GetSpellInfo then
        local ok, info = pcall(C_Spell.GetSpellInfo, spellId)
        if ok and type(info) == "table" then
            local name = ns.Str(info.name)
            if name and name ~= "" then
                return name
            end
        end
    end
    if type(GetSpellInfo) == "function" then
        local ok, name = pcall(GetSpellInfo, spellId)
        if ok then
            return ns.Str(name) or ""
        end
    end
    return ""
end

function ns.InitNpcs()
    local function onOpen(kind)
        if not ns.sessionOpen then
            return
        end
        local name, npcId = ns.InteractNpc()
        local zone, _, map, x, y = ns.Where()
        openedAt[kind] = time()
        ns.Emit("npc", "npcs", kind, name, npcId, zone, map, x, y)
    end

    local function onClose(kind)
        if not ns.sessionOpen then
            return
        end
        local started = openedAt[kind]
        openedAt[kind] = nil
        local duration = ""
        if started then
            duration = time() - started
        end
        ns.Emit("npc_close", "npcs", kind, duration)
    end

    for i = 1, #WINDOWS do
        local openEvent, closeEvent, kind = WINDOWS[i][1], WINDOWS[i][2], WINDOWS[i][3]
        ns.Register(openEvent, function()
            onOpen(kind)
        end)
        ns.Register(closeEvent, function()
            onClose(kind)
        end)
    end

    ns.Register("HEARTHSTONE_BOUND", function()
        if not ns.sessionOpen then
            return
        end
        local zone, sub = ns.Where()
        ns.Emit("bind", "travel", zone, sub)
    end)

    ns.Register("LEARNED_SPELL_IN_TAB", function(_, spellId)
        if not ns.sessionOpen then
            return
        end
        spellId = ns.Num(spellId)
        ns.Emit("spell_learned", "skills", spellId or "", spellName(spellId), ns.lastLevel or 0)
    end)
end
