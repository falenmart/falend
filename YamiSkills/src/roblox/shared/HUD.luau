--[[
	HUD (client) - yetenek çubuğu: tuş, isim, bekleme süresi, kombo göstergesi.
	Slotlar tıklanabilir (mobil / fare). Katana kuşanılınca görünür.
]]
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")

local Config = require(script.Parent:WaitForChild("Config"))

local HUD = {}
HUD.OnActivate = nil :: ((string) -> ())?

local slots: { [string]: any } = {}
local cooldownEnd: { [string]: number } = {}
local cooldownTotal: { [string]: number } = {}
local gui: ScreenGui? = nil
local bar: Frame? = nil
local comboDots: { Frame } = {}
local visible = false
local blackBladeEnd = 0

local function keyLabel(skill: string): string
	local binds = Config.Keybinds[skill]
	if binds == nil then
		return ""
	end
	local touch = UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
	if touch then
		return ""
	end
	for _, k in ipairs(binds) do
		local n = k.Name
		if #n == 1 then
			return n
		end
	end
	return binds[1].Name
end

local function make(className: string, props: { [string]: any }, parent: Instance?)
	local inst = Instance.new(className)
	for k, v in pairs(props) do
		(inst :: any)[k] = v
	end
	if parent then
		inst.Parent = parent
	end
	return inst
end

local function build()
	local player = Players.LocalPlayer
	local g = make("ScreenGui", {
		Name = "YamiHUD",
		ResetOnSpawn = false,
		DisplayOrder = 10,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Enabled = true,
	}) :: ScreenGui
	local n = #Config.SkillOrder
	local slotSize, gap = 74, 8
	local width = n * slotSize + (n - 1) * gap
	local b = make("Frame", {
		Name = "Bar",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, 140),
		Size = UDim2.new(0, width, 0, slotSize + 34),
		BackgroundTransparency = 1,
	}, g) :: Frame
	make("TextLabel", {
		Name = "Title",
		BackgroundTransparency = 1,
		Size = UDim2.new(1, 0, 0, 16),
		Position = UDim2.new(0, 0, 0, 0),
		Font = Enum.Font.GothamBold,
		Text = "闇魔法  ·  KARANLIK BÜYÜ",
		TextColor3 = Color3.new(1, 1, 1),
		TextTransparency = 0.25,
		TextStrokeTransparency = 0.4,
		TextSize = 13,
	}, b)
	local dots = make("Frame", {
		Name = "Combo",
		BackgroundTransparency = 1,
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, 0, 0, 3),
		Size = UDim2.new(0, 60, 0, 10),
	}, b)
	make("UIListLayout", {
		FillDirection = Enum.FillDirection.Horizontal,
		HorizontalAlignment = Enum.HorizontalAlignment.Right,
		Padding = UDim.new(0, 5),
	}, dots)
	for i = 1, 4 do
		local d = make("Frame", {
			Name = "Dot" .. i,
			Size = UDim2.new(0, 9, 0, 9),
			BackgroundColor3 = Color3.new(1, 1, 1),
			BackgroundTransparency = 0.75,
			LayoutOrder = i,
		}, dots) :: Frame
		make("UICorner", { CornerRadius = UDim.new(1, 0) }, d)
		comboDots[i] = d
	end
	for i, skill in ipairs(Config.SkillOrder) do
		local x = (i - 1) * (slotSize + gap)
		local btn = make("TextButton", {
			Name = skill,
			AutoButtonColor = false,
			Text = "",
			Position = UDim2.new(0, x, 0, 22),
			Size = UDim2.new(0, slotSize, 0, slotSize),
			BackgroundColor3 = Color3.fromRGB(4, 4, 6),
			BackgroundTransparency = 0.12,
		}, b) :: TextButton
		make("UICorner", { CornerRadius = UDim.new(0, 8) }, btn)
		local stroke = make("UIStroke", {
			Color = Color3.new(1, 1, 1),
			Thickness = 1.5,
			Transparency = 0.55,
			ApplyStrokeMode = Enum.ApplyStrokeMode.Border,
		}, btn) :: UIStroke
		make("TextLabel", {
			Name = "Key",
			BackgroundTransparency = 1,
			Position = UDim2.new(0, 6, 0, 3),
			Size = UDim2.new(0, 22, 0, 18),
			Font = Enum.Font.GothamBlack,
			Text = keyLabel(skill),
			TextColor3 = Color3.new(1, 1, 1),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextSize = 16,
			ZIndex = 3,
		}, btn)
		make("TextLabel", {
			Name = "SkillName",
			BackgroundTransparency = 1,
			AnchorPoint = Vector2.new(0.5, 1),
			Position = UDim2.new(0.5, 0, 1, -4),
			Size = UDim2.new(1, -8, 0, 26),
			Font = Enum.Font.GothamBold,
			Text = Config.SkillNames[skill] or skill,
			TextColor3 = Color3.new(1, 1, 1),
			TextWrapped = true,
			TextScaled = true,
			ZIndex = 3,
		}, btn)
		local overlay = make("Frame", {
			Name = "Cooldown",
			AnchorPoint = Vector2.new(0, 1),
			Position = UDim2.new(0, 0, 1, 0),
			Size = UDim2.new(1, 0, 0, 0),
			BackgroundColor3 = Color3.new(0, 0, 0),
			BackgroundTransparency = 0.25,
			BorderSizePixel = 0,
			ZIndex = 4,
		}, btn) :: Frame
		make("UICorner", { CornerRadius = UDim.new(0, 8) }, overlay)
		local cdText = make("TextLabel", {
			Name = "Time",
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 1, 0),
			Font = Enum.Font.GothamBlack,
			Text = "",
			TextColor3 = Color3.new(1, 1, 1),
			TextSize = 22,
			TextStrokeTransparency = 0.3,
			ZIndex = 5,
		}, btn) :: TextLabel
		btn.Activated:Connect(function()
			if HUD.OnActivate then
				HUD.OnActivate(skill)
			end
		end)
		slots[skill] = { button = btn, overlay = overlay, text = cdText, stroke = stroke, ready = true }
	end
	g.Parent = player:WaitForChild("PlayerGui")
	gui = g
	bar = b
end

local function flash(slot)
	local s = slot.stroke :: UIStroke
	s.Transparency = 0
	s.Thickness = 3
	TweenService:Create(s, TweenInfo.new(0.45), { Transparency = 0.55, Thickness = 1.5 }):Play()
end

function HUD.Init()
	if gui then
		return
	end
	build()
	RunService.RenderStepped:Connect(function()
		local now = os.clock()
		for skill, slot in pairs(slots) do
			local endT = cooldownEnd[skill]
			if endT and endT > now then
				local total = cooldownTotal[skill] or 1
				local frac = math.clamp((endT - now) / total, 0, 1)
				slot.overlay.Size = UDim2.new(1, 0, frac, 0)
				local remain = endT - now
				slot.text.Text = if remain >= 10
					then string.format("%d", math.ceil(remain))
					else string.format("%.1f", remain)
				slot.ready = false
			elseif not slot.ready then
				slot.ready = true
				slot.overlay.Size = UDim2.new(1, 0, 0, 0)
				slot.text.Text = ""
				flash(slot)
			end
		end
		local bb = slots.BlackBlade
		if bb then
			if blackBladeEnd > now then
				local pulse = 0.5 + 0.5 * math.sin(now * 8)
				bb.stroke.Thickness = 2 + pulse * 1.5
				bb.stroke.Transparency = 0.1 * pulse
			end
		end
	end)
end

function HUD.SetVisible(v: boolean)
	if bar == nil or visible == v then
		return
	end
	visible = v
	local b = bar :: Frame
	TweenService:Create(b, TweenInfo.new(0.3, Enum.EasingStyle.Quart), {
		Position = if v then UDim2.new(0.5, 0, 1, -14) else UDim2.new(0.5, 0, 1, 140),
	}):Play()
end

function HUD.StartCooldown(skill: string, duration: number)
	if duration <= 0 then
		return
	end
	cooldownEnd[skill] = os.clock() + duration
	cooldownTotal[skill] = duration
end

function HUD.ResetCooldown(skill: string)
	cooldownEnd[skill] = nil
end

function HUD.Remaining(skill: string): number
	local e = cooldownEnd[skill]
	return if e then math.max(0, e - os.clock()) else 0
end

function HUD.SetCombo(index: number)
	for i, d in ipairs(comboDots) do
		d.BackgroundTransparency = if i <= index then 0.05 else 0.75
	end
end

function HUD.SetBlackBlade(duration: number)
	blackBladeEnd = os.clock() + duration
	local bb = slots.BlackBlade
	if bb then
		task.delay(duration, function()
			if os.clock() >= blackBladeEnd - 0.05 then
				bb.stroke.Thickness = 1.5
				bb.stroke.Transparency = 0.55
			end
		end)
	end
end

return HUD
