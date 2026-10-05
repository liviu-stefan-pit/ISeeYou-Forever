local addonName, ns = ...

ns.handlers = {}
ns.frame = CreateFrame("Frame")

function ns.Register(event, handler)
    local list = ns.handlers[event]
    if not list then
        list = {}
        ns.handlers[event] = list
        pcall(ns.frame.RegisterEvent, ns.frame, event)
    end
    list[#list + 1] = handler
end

function ns.InitDB()
    if type(ISYF_DB) ~= "table" then
        ISYF_DB = {}
    end
    if type(ISYF_DB.nextId) ~= "number" then
        ISYF_DB.nextId = 1
    end
    if type(ISYF_DB.keepSessions) ~= "number" then
        ISYF_DB.keepSessions = 10
    end

    if type(ISYF_Char) ~= "table" then
        ISYF_Char = {}
    end
    if type(ISYF_Char.events) ~= "table" then
        ISYF_Char.events = {}
    end
    if type(ISYF_Char.track) ~= "table" then
        ISYF_Char.track = {}
    end
    if type(ISYF_Char.nextId) ~= "number" then
        ISYF_Char.nextId = 1
    end
    if type(ISYF_Char.quests) ~= "table" then
        ISYF_Char.quests = {}
    end
    for i = 1, #ns.CATEGORIES do
        local key = ns.CATEGORIES[i].key
        if ISYF_Char.track[key] == nil then
            ISYF_Char.track[key] = true
        end
    end
end

ns.frame:SetScript("OnEvent", function(_, event, ...)
    if event == "ADDON_LOADED" then
        local loaded = ...
        if loaded ~= addonName then
            return
        end
        ns.InitDB()
        ns.InitSession()
        ns.InitExperience()
        ns.InitQuests()
        ns.InitEconomy()
        ns.InitEngagements()
        ns.InitRoutes()
        ns.InitWorld()
        ns.InitUI()
        ns.frame:UnregisterEvent("ADDON_LOADED")
        return
    end

    local list = ns.handlers[event]
    if not list then
        return
    end
    for i = 1, #list do
        local ok, err = pcall(list[i], event, ...)
        if not ok then
            ns.Print(event .. " failed: " .. tostring(err))
        end
    end
end)

ns.frame:RegisterEvent("ADDON_LOADED")
