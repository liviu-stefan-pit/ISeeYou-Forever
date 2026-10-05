local addonName, ns = ...

local window
local statusText
local pathBox
local checks = {}
local loggerChecks = {}

function ns.SetWikiPath(text)
    if type(ISYF_DB) ~= "table" then
        return
    end
    text = strtrim(text or "")
    if ISYF_DB.wikiPath == text then
        return
    end
    ISYF_DB.wikiPath = text
    if text == "" then
        ns.Print("Wiki folder cleared. Logout still updates the default wiki.")
    else
        ns.Print("Wiki folder saved. It is built there from your log the next time you log out.")
    end
end

local function applyTrack(key, on)
    if not ISYF_Char or not ISYF_Char.track then
        return
    end
    ISYF_Char.track[key] = on and true or false
    if key == "routes" and ns.SyncRouteSampler then
        ns.SyncRouteSampler()
    end
end

local function setAll(on)
    for i = 1, #ns.CATEGORIES do
        local key = ns.CATEGORIES[i].key
        applyTrack(key, on)
        local check = checks[key]
        if check then
            check:SetChecked(on)
        end
    end
end

function ns.RefreshStatus()
    if not statusText or not window or not window:IsShown() then
        return
    end
    local session = ISYF_Char and ISYF_Char.session
    if not session then
        statusText:SetText("Waiting for login.")
        return
    end
    local elapsed = time() - (session.start or time())
    statusText:SetText(string.format(
        "Session %s    XP %d    +%s    -%s",
        ns.FormatDuration(elapsed),
        session.xp or 0,
        ns.FormatCopper(session.copperIn or 0),
        ns.FormatCopper(session.copperOut or 0)
    ))
end

local function buildWindow()
    local ok, frame = pcall(CreateFrame, "Frame", nil, UIParent, "BasicFrameTemplateWithInset")
    if not ok or not frame then
        frame = CreateFrame("Frame", nil, UIParent, "BackdropTemplate")
        frame:SetBackdrop({
            bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
            edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
            tile = true,
            tileSize = 32,
            edgeSize = 32,
            insets = { left = 11, right = 12, top = 12, bottom = 11 },
        })
    end
    frame:SetSize(560, 756)
    frame:SetPoint("CENTER")
    frame:SetMovable(true)
    frame:EnableMouse(true)
    frame:RegisterForDrag("LeftButton")
    frame:SetScript("OnDragStart", frame.StartMoving)
    frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
    frame:SetClampedToScreen(true)
    frame:Hide()

    local title = frame.TitleText
    if not title and frame.TitleContainer then
        title = frame.TitleContainer.TitleText
    end
    if title then
        title:SetText("I see you forever")
    else
        title = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
        title:SetPoint("TOP", 0, -10)
        title:SetText("I see you forever")
    end

    statusText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    statusText:SetPoint("TOPLEFT", 16, -36)
    statusText:SetPoint("TOPRIGHT", -16, -36)
    statusText:SetJustifyH("LEFT")
    statusText:SetText("Waiting for login.")

    local y = -68
    for i = 1, #ns.CATEGORIES do
        local category = ns.CATEGORIES[i]
        local check = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
        check:SetPoint("TOPLEFT", 16, y)
        check:SetChecked(ns.Enabled(category.key))
        check.key = category.key
        local label = check:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
        label:SetPoint("LEFT", check, "RIGHT", 2, 0)
        label:SetText(category.label)
        check:SetScript("OnClick", function(self)
            applyTrack(self.key, self:GetChecked())
        end)
        checks[category.key] = check
        y = y - 26
    end

    local pathLabel = frame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    pathLabel:SetPoint("BOTTOMLEFT", 16, 116)
    pathLabel:SetText("Wiki folder")

    pathBox = CreateFrame("EditBox", nil, frame, "InputBoxTemplate")
    pathBox:SetSize(500, 20)
    pathBox:SetPoint("BOTTOMLEFT", 22, 90)
    pathBox:SetAutoFocus(false)
    pathBox:SetMaxLetters(240)
    pathBox:SetFontObject(GameFontHighlightSmall)
    pathBox:SetScript("OnEnterPressed", function(self)
        ns.SetWikiPath(self:GetText())
        self:ClearFocus()
    end)
    pathBox:SetScript("OnEscapePressed", function(self)
        self:SetText((ISYF_DB and ISYF_DB.wikiPath) or "")
        self:ClearFocus()
    end)
    pathBox:SetScript("OnEditFocusLost", function(self)
        ns.SetWikiPath(self:GetText())
    end)

    local function loggerOption(key, label, x, setter, getter)
        local check = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
        check:SetPoint("BOTTOMLEFT", x, 48)
        check:SetChecked(getter())
        local text = check:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
        text:SetPoint("LEFT", check, "RIGHT", 0, 1)
        text:SetText(label)
        check:SetScript("OnClick", function(self)
            setter(self:GetChecked())
        end)
        loggerChecks[key] = check
    end

    loggerOption("shown", "Show logger", 12, ns.SetLoggerShown, ns.LoggerShown)
    loggerOption("locked", "Lock logger", 160, ns.SetLoggerLocked, ns.LoggerLocked)
    loggerOption("routes", "Show route dots", 310, ns.SetLoggerRoutes, ns.LoggerRoutes)

    local allOn = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    allOn:SetSize(100, 24)
    allOn:SetPoint("BOTTOMLEFT", 16, 14)
    allOn:SetText("All on")
    allOn:SetScript("OnClick", function()
        setAll(true)
    end)

    local allOff = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    allOff:SetSize(100, 24)
    allOff:SetPoint("LEFT", allOn, "RIGHT", 8, 0)
    allOff:SetText("All off")
    allOff:SetScript("OnClick", function()
        setAll(false)
    end)

    local ticker = 0
    frame:SetScript("OnUpdate", function(_, elapsed)
        ticker = ticker + elapsed
        if ticker < 1 then
            return
        end
        ticker = 0
        ns.RefreshStatus()
    end)
    frame:SetScript("OnShow", function()
        for i = 1, #ns.CATEGORIES do
            local category = ns.CATEGORIES[i]
            checks[category.key]:SetChecked(ns.Enabled(category.key))
        end
        ns.RefreshStatus()
        if pathBox then
            pathBox:SetText((ISYF_DB and ISYF_DB.wikiPath) or "")
        end
        ns.RefreshLoggerChecks()
    end)

    window = frame
end

function ns.Toggle()
    if not window then
        buildWindow()
    end
    if window:IsShown() then
        window:Hide()
    else
        window:Show()
    end
end

function ns.InitUI()
end

function ns.RefreshLoggerChecks()
    if loggerChecks.shown and ns.LoggerShown then
        loggerChecks.shown:SetChecked(ns.LoggerShown())
    end
    if loggerChecks.locked and ns.LoggerLocked then
        loggerChecks.locked:SetChecked(ns.LoggerLocked())
    end
    if loggerChecks.routes and ns.LoggerRoutes then
        loggerChecks.routes:SetChecked(ns.LoggerRoutes())
    end
end

SLASH_ISEEYOUFOREVER1 = "/isy"
SlashCmdList.ISEEYOUFOREVER = function(msg)
    msg = strtrim(msg or ""):lower()
    if msg == "log" then
        if ns.ToggleLogger then
            ns.ToggleLogger()
        end
        return
    end
    if msg == "reset" then
        if ns.ResetLogger then
            ns.ResetLogger()
        end
        return
    end
    ns.Toggle()
end

function ISYF_CompartmentClick()
    ns.Toggle()
end
