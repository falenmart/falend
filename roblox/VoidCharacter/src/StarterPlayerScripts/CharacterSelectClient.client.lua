-- CharacterSelectClient (LocalScript) -> StarterPlayer > StarterPlayerScripts
-- Karakter seçim menüsü. Sol üstteki butona ya da M tuşuna basınca açılır.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")
local TweenService = game:GetService("TweenService")

print("[Select] CharacterSelectClient başladı")
local CharacterList = require(ReplicatedStorage:WaitForChild("CharacterList"))
local remote = ReplicatedStorage:WaitForChild("SelectCharacter", 10)
if not remote then
	error("[Select] SelectCharacter yok -> CharacterSelectServer çalışmıyor (ServerScriptService'te Script olmalı)")
end

local player = Players.LocalPlayer
local OPEN_KEY = Enum.KeyCode.M

local gui = Instance.new("ScreenGui")
gui.Name = "CharacterSelect"
gui.ResetOnSpawn = false
gui.DisplayOrder = 10
gui.Parent = player:WaitForChild("PlayerGui")

-- Açma butonu
local openBtn = Instance.new("TextButton")
openBtn.Position = UDim2.fromOffset(16, 70)
openBtn.Size = UDim2.fromOffset(150, 40)
openBtn.BackgroundColor3 = Color3.fromRGB(15, 15, 20)
openBtn.BackgroundTransparency = 0.15
openBtn.Font = Enum.Font.GothamBold
openBtn.TextSize = 16
openBtn.TextColor3 = Color3.new(1, 1, 1)
openBtn.Text = "Karakter Seç (M)"
openBtn.Parent = gui
Instance.new("UICorner", openBtn).CornerRadius = UDim.new(0, 8)

-- Panel
local shade = Instance.new("Frame")
shade.Size = UDim2.fromScale(1, 1)
shade.BackgroundColor3 = Color3.new(0, 0, 0)
shade.BackgroundTransparency = 0.45
shade.Visible = false
shade.Parent = gui

local panel = Instance.new("Frame")
panel.AnchorPoint = Vector2.new(0.5, 0.5)
panel.Position = UDim2.fromScale(0.5, 0.5)
panel.Size = UDim2.new(0, 760, 0, 380)
panel.BackgroundColor3 = Color3.fromRGB(12, 12, 16)
panel.Parent = shade
Instance.new("UICorner", panel).CornerRadius = UDim.new(0, 14)
local sizeLimit = Instance.new("UISizeConstraint")
sizeLimit.MaxSize = Vector2.new(760, 380)
sizeLimit.Parent = panel

local title = Instance.new("TextLabel")
title.Position = UDim2.fromOffset(24, 14)
title.Size = UDim2.new(1, -80, 0, 40)
title.BackgroundTransparency = 1
title.Font = Enum.Font.GothamBlack
title.TextSize = 28
title.TextXAlignment = Enum.TextXAlignment.Left
title.TextColor3 = Color3.new(1, 1, 1)
title.Text = "KARAKTERİNİ SEÇ"
title.Parent = panel

local close = Instance.new("TextButton")
close.AnchorPoint = Vector2.new(1, 0)
close.Position = UDim2.new(1, -14, 0, 14)
close.Size = UDim2.fromOffset(40, 40)
close.BackgroundTransparency = 1
close.Font = Enum.Font.GothamBlack
close.TextSize = 24
close.TextColor3 = Color3.fromRGB(180, 180, 190)
close.Text = "X"
close.Parent = panel

local list = Instance.new("Frame")
list.Position = UDim2.fromOffset(20, 70)
list.Size = UDim2.new(1, -40, 1, -90)
list.BackgroundTransparency = 1
list.Parent = panel
local layout = Instance.new("UIListLayout")
layout.FillDirection = Enum.FillDirection.Horizontal
layout.Padding = UDim.new(0, 14)
layout.HorizontalAlignment = Enum.HorizontalAlignment.Center
layout.Parent = list

local cards = {}
for i, c in ipairs(CharacterList) do
	local card = Instance.new("Frame")
	card.LayoutOrder = i
	card.Size = UDim2.new(1 / #CharacterList, -10, 1, 0)
	card.BackgroundColor3 = c.Color
	card.Parent = list
	Instance.new("UICorner", card).CornerRadius = UDim.new(0, 12)
	local stroke = Instance.new("UIStroke", card)
	stroke.Color = c.Accent
	stroke.Thickness = 2
	stroke.Transparency = 0.8

	local name = Instance.new("TextLabel")
	name.Position = UDim2.fromOffset(14, 12)
	name.Size = UDim2.new(1, -28, 0, 30)
	name.BackgroundTransparency = 1
	name.Font = Enum.Font.GothamBlack
	name.TextScaled = true
	name.TextXAlignment = Enum.TextXAlignment.Left
	name.TextColor3 = c.Accent
	name.Text = c.Name
	name.Parent = card

	local desc = Instance.new("TextLabel")
	desc.Position = UDim2.fromOffset(14, 50)
	desc.Size = UDim2.new(1, -28, 0, 110)
	desc.BackgroundTransparency = 1
	desc.Font = Enum.Font.Gotham
	desc.TextSize = 15
	desc.TextWrapped = true
	desc.TextXAlignment = Enum.TextXAlignment.Left
	desc.TextYAlignment = Enum.TextYAlignment.Top
	desc.TextColor3 = Color3.fromRGB(215, 215, 222)
	desc.Text = c.Description
	desc.Parent = card

	local keys = Instance.new("TextLabel")
	keys.Position = UDim2.new(0, 14, 1, -110)
	keys.Size = UDim2.new(1, -28, 0, 44)
	keys.BackgroundTransparency = 1
	keys.Font = Enum.Font.GothamMedium
	keys.TextSize = 13
	keys.TextWrapped = true
	keys.TextXAlignment = Enum.TextXAlignment.Left
	keys.TextYAlignment = Enum.TextYAlignment.Top
	keys.TextColor3 = Color3.fromRGB(160, 160, 170)
	keys.Text = c.Keys
	keys.Parent = card

	local pick = Instance.new("TextButton")
	pick.AnchorPoint = Vector2.new(0.5, 1)
	pick.Position = UDim2.new(0.5, 0, 1, -12)
	pick.Size = UDim2.new(1, -28, 0, 44)
	pick.BackgroundColor3 = c.Accent
	pick.Font = Enum.Font.GothamBlack
	pick.TextSize = 18
	pick.TextColor3 = Color3.fromRGB(10, 10, 12)
	pick.Text = "SEÇ"
	pick.Parent = card
	Instance.new("UICorner", pick).CornerRadius = UDim.new(0, 8)

	cards[c.Id] = { stroke = stroke, pick = pick }
	pick.MouseButton1Click:Connect(function()
		if player:GetAttribute("SelectedCharacter") == c.Id then
			shade.Visible = false
			return
		end
		remote:FireServer(c.Id)
		shade.Visible = false
	end)
end

local function refresh()
	local current = player:GetAttribute("SelectedCharacter")
	for id, card in pairs(cards) do
		local selected = id == current
		card.stroke.Transparency = selected and 0 or 0.8
		card.pick.Text = selected and "SEÇİLİ" or "SEÇ"
	end
	local entry
	for _, c in ipairs(CharacterList) do
		if c.Id == current then
			entry = c
		end
	end
	openBtn.Text = (entry and entry.Name or "Karakter") .. " (M)"
end

local function toggle()
	shade.Visible = not shade.Visible
	if shade.Visible then
		refresh()
		panel.Size = UDim2.new(0, 700, 0, 350)
		TweenService:Create(panel, TweenInfo.new(0.2, Enum.EasingStyle.Back), { Size = UDim2.new(0, 760, 0, 380) }):Play()
	end
end

openBtn.MouseButton1Click:Connect(toggle)
close.MouseButton1Click:Connect(function()
	shade.Visible = false
end)
UserInputService.InputBegan:Connect(function(input, processed)
	if not processed and input.KeyCode == OPEN_KEY then
		toggle()
	end
end)
player:GetAttributeChangedSignal("SelectedCharacter"):Connect(refresh)
refresh()

-- İlk girişte menüyü otomatik aç
task.delay(1, function()
	local current = player:GetAttribute("SelectedCharacter")
	if current == nil or current == "None" then
		if not shade.Visible then
			toggle()
		end
	end
end)

print("[Select] CharacterSelectClient hazır")
