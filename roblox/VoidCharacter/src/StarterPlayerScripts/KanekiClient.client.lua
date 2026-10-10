-- KanekiClient (LocalScript) -> StarterPlayer > StarterPlayerScripts
-- Kagune dokunaçlarını (her Kaneki oyuncusu için) çizer ve canlandırır,
-- kakugan (kırmızı göz), HUD, tuşlar ve kamera sarsıntısı.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

print("[Kaneki] KanekiClient başladı")
local kc = ReplicatedStorage:WaitForChild("KanekiConfig", 5)
if not kc then
	error("[Kaneki] ReplicatedStorage içinde 'KanekiConfig' ModuleScript'i yok! Paketten ReplicatedStorage'a taşı.")
end
local K = require(kc)
local remotes = ReplicatedStorage:WaitForChild("KanekiRemotes", 10)
if not remotes then
	error("[Kaneki] KanekiRemotes yok -> KanekiServer çalışmıyor (ServerScriptService'te Script olmalı)")
end
local abilityRemote = remotes:WaitForChild("Ability")
local fxRemote = remotes:WaitForChild("Fx")

local player = Players.LocalPlayer
local camera = workspace.CurrentCamera

local function isKaneki()
	return player:GetAttribute("SelectedCharacter") == "Kaneki"
end

local function tween(obj, time, props, style)
	local t = TweenService:Create(obj, TweenInfo.new(time, style or Enum.EasingStyle.Quad), props)
	t:Play()
	return t
end

---------------------------------------------------------------------
-- HUD
---------------------------------------------------------------------
local gui = Instance.new("ScreenGui")
gui.Name = "KanekiHUD"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")

local bar = Instance.new("Frame")
bar.AnchorPoint = Vector2.new(0.5, 1)
bar.Position = UDim2.new(0.5, 0, 1, -20)
bar.Size = UDim2.fromOffset(4 * 74, 64)
bar.BackgroundTransparency = 1
bar.Parent = gui
local layout = Instance.new("UIListLayout")
layout.FillDirection = Enum.FillDirection.Horizontal
layout.HorizontalAlignment = Enum.HorizontalAlignment.Center
layout.Padding = UDim.new(0, 10)
layout.SortOrder = Enum.SortOrder.LayoutOrder
layout.Parent = bar

local slots = {}
local function makeSlot(order, id, key, title)
	local f = Instance.new("Frame")
	f.LayoutOrder = order
	f.Size = UDim2.fromOffset(64, 64)
	f.BackgroundColor3 = Color3.fromRGB(20, 4, 6)
	f.BackgroundTransparency = 0.15
	f.ClipsDescendants = true
	f.Parent = bar
	Instance.new("UICorner", f).CornerRadius = UDim.new(0, 10)
	local stroke = Instance.new("UIStroke", f)
	stroke.Color = K.Kagune.TipColor
	stroke.Transparency = 0.6
	local cd = Instance.new("Frame")
	cd.AnchorPoint = Vector2.new(0, 1)
	cd.Position = UDim2.fromScale(0, 1)
	cd.Size = UDim2.fromScale(1, 0)
	cd.BackgroundColor3 = Color3.new(0, 0, 0)
	cd.BackgroundTransparency = 0.35
	cd.BorderSizePixel = 0
	cd.Parent = f
	local k = Instance.new("TextLabel")
	k.BackgroundTransparency = 1
	k.Size = UDim2.new(1, 0, 0.55, 0)
	k.Font = Enum.Font.GothamBlack
	k.TextScaled = true
	k.TextColor3 = Color3.fromRGB(255, 225, 225)
	k.Text = key
	k.Parent = f
	local t = Instance.new("TextLabel")
	t.BackgroundTransparency = 1
	t.Position = UDim2.fromScale(0, 0.58)
	t.Size = UDim2.new(1, 0, 0.32, 0)
	t.Font = Enum.Font.GothamBold
	t.TextScaled = true
	t.TextColor3 = Color3.fromRGB(190, 120, 125)
	t.Text = title
	t.Parent = f
	slots[id] = { cd = cd, stroke = stroke }
end
makeSlot(1, "Kagune", K.Keys.Kagune.Name, "Kagune")
makeSlot(2, "Strike", K.Keys.Strike.Name, "Saplama")
makeSlot(3, "Flurry", K.Keys.Flurry.Name, "Fırtına")
makeSlot(4, "Grab", K.Keys.Grab.Name, "Yakalama")

local function refreshHUD()
	bar.Visible = isKaneki()
	local char = player.Character
	local out = char and char:GetAttribute("KaguneOut") == true
	slots.Kagune.stroke.Transparency = out and 0 or 0.6
	slots.Kagune.stroke.Thickness = out and 2 or 1
	for _, id in ipairs({ "Strike", "Flurry", "Grab" }) do
		slots[id].stroke.Transparency = out and 0.3 or 0.9
	end
end
player:GetAttributeChangedSignal("SelectedCharacter"):Connect(refreshHUD)

---------------------------------------------------------------------
-- Kamera sarsıntısı
---------------------------------------------------------------------
local shakeUntil, shakePower = 0, 0
RunService:BindToRenderStep("KanekiShake", Enum.RenderPriority.Camera.Value + 3, function()
	local now = os.clock()
	if now < shakeUntil then
		local p = shakePower * math.min(1, (shakeUntil - now) * 2)
		camera.CFrame *= CFrame.Angles(
			math.rad((math.random() - 0.5) * p * 2),
			math.rad((math.random() - 0.5) * p * 2),
			0
		)
	end
end)

---------------------------------------------------------------------
-- Kagune çizimi
---------------------------------------------------------------------
-- Dokunaçlar belin arkasından çıkar. base: gövdeye göre çıkış noktası, dir: dinlenme yönü (arka = +Z)
local TENTACLES = {
	{ base = Vector3.new(-0.35, -0.55, 0.5), dir = Vector3.new(-1.1, 1.6, 1.4), len = 1.0, phase = 0.0 },
	{ base = Vector3.new(0.35, -0.55, 0.5), dir = Vector3.new(1.1, 1.6, 1.4), len = 1.0, phase = 1.7 },
	{ base = Vector3.new(-0.25, -0.8, 0.5), dir = Vector3.new(-1.8, 0.25, 1.1), len = 0.9, phase = 3.1 },
	{ base = Vector3.new(0.25, -0.8, 0.5), dir = Vector3.new(1.8, 0.25, 1.1), len = 0.9, phase = 4.4 },
}

local renders = {} -- [character] = render
local localFolder = Instance.new("Folder")
localFolder.Name = "KaguneLocal"
localFolder.Parent = workspace

local function newPart(shape, color, material)
	local p = Instance.new("Part")
	p.Shape = shape
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Material = material or Enum.Material.Neon
	p.Color = color
	p.Size = Vector3.new(0.1, 0.1, 0.1)
	p.Parent = localFolder
	return p
end

local function createRender(char)
	local r = { char = char, grow = 0, tentacles = {}, action = nil }
	local n = K.Kagune.Segments
	for i = 1, #TENTACLES do
		local segs, joints = {}, {}
		for s = 1, n do
			local t = (s - 1) / (n - 1)
			local color = K.Kagune.BaseColor:Lerp(K.Kagune.TipColor, t ^ 0.7)
			-- Neon ile hafif parlayan, pul pul görünen dokunaç
			segs[s] = newPart(Enum.PartType.Cylinder, color, (s % 3 == 0) and Enum.Material.Neon or Enum.Material.SmoothPlastic)
			joints[s] = newPart(Enum.PartType.Ball, color, Enum.Material.Neon)
		end
		r.tentacles[i] = { segs = segs, joints = joints }
	end
	-- Kakugan: siyah göz akı + kırmızı iris (sol göz)
	r.sclera = newPart(Enum.PartType.Block, Color3.new(0, 0, 0), Enum.Material.SmoothPlastic)
	r.iris = newPart(Enum.PartType.Block, K.EyeColor, Enum.Material.Neon)
	local light = Instance.new("PointLight")
	light.Color = K.EyeColor
	light.Range = 4
	light.Brightness = 1.5
	light.Parent = r.iris
	r.light = Instance.new("PointLight")
	r.light.Color = K.Kagune.TipColor
	r.light.Range = 10
	r.light.Brightness = 0
	r.light.Parent = r.tentacles[1].joints[1]
	renders[char] = r
	return r
end

local function destroyRender(char)
	local r = renders[char]
	if not r then
		return
	end
	for _, tent in ipairs(r.tentacles) do
		for _, p in ipairs(tent.segs) do
			p:Destroy()
		end
		for _, p in ipairs(tent.joints) do
			p:Destroy()
		end
	end
	r.sclera:Destroy()
	r.iris:Destroy()
	renders[char] = nil
end

local function bezier(a, b, c, t)
	local u = 1 - t
	return a * (u * u) + b * (2 * u * t) + c * (t * t)
end

local function smoothstep(x)
	x = math.clamp(x, 0, 1)
	return x * x * (3 - 2 * x)
end

-- Saldırı sırasında dokunaçların ne kadar hedefe uzandığı (0..1)
local function actionAmount(action, now)
	local e = now - action.start
	if e < 0 or e > action.dur then
		return 0
	end
	local inT = action.kind == "Strike" and 0.08 or 0.15
	return smoothstep(e / inT) * smoothstep((action.dur - e) / 0.25)
end

local function hash(n)
	return (math.sin(n * 12.9898) * 43758.5453) % 1
end

local function actionGoal(action, i, now, root, base)
	if action.kind == "Strike" then
		local off = Vector3.new(((i - 1) % 2) * 2 - 1, (i <= 2) and 0.6 or -0.6, 0) * 0.6
		return action.target + off
	elseif action.kind == "Grab" then
		local tr = action.target
		local p = (typeof(tr) == "Instance" and tr.Parent) and tr.Position or base
		local a = i * math.pi / 2 + now * 5
		return p + Vector3.new(math.cos(a) * 1.3, (i - 2.5) * 0.7, math.sin(a) * 1.3)
	elseif action.kind == "Flurry" then
		-- Her dokunaç farklı ritimde rastgele yönlere saplar
		local beat = (now - action.start) / 0.18 + i * 0.5
		local idx = math.floor(beat)
		local ang = hash(idx * 7.13 + i * 3.7) * math.pi * 2
		local h = hash(idx * 2.31 + i) * 3 - 1
		local frac = beat - idx
		local reach = 4 + math.sin(frac * math.pi) * 9
		return root.Position + Vector3.new(math.cos(ang) * reach, h, math.sin(ang) * reach)
	end
	return base
end

local function updateRender(r, dt, now)
	local char = r.char
	local torso = char:FindFirstChild("UpperTorso") or char:FindFirstChild("Torso")
	local root = char:FindFirstChild("HumanoidRootPart")
	local head = char:FindFirstChild("Head")
	if not (char.Parent and torso and root) then
		destroyRender(char)
		return
	end
	local out = char:GetAttribute("KaguneOut") == true
	if out then
		r.grow = math.min(1, r.grow + dt / 0.45)
	else
		r.grow = math.max(0, r.grow - dt / 0.35)
		if r.grow <= 0 then
			destroyRender(char)
			return
		end
	end
	-- Açılırken hafif taşan (elastik) büyüme
	local g = r.grow
	local gScale = g < 1 and (1 - (1 - g) ^ 3) * (1 + 0.15 * math.sin(g * math.pi)) or 1

	local tcf = torso.CFrame
	local vel = root.AssemblyLinearVelocity
	local trail = -Vector3.new(vel.X, 0, vel.Z) * 0.07
	if trail.Magnitude > 4 then
		trail = trail.Unit * 4
	end
	local moving = Vector3.new(vel.X, 0, vel.Z).Magnitude > 2
	local action = r.action
	if action and now - action.start > action.dur then
		r.action = nil
		action = nil
	end

	local n = K.Kagune.Segments
	for i, def in ipairs(TENTACLES) do
		local tent = r.tentacles[i]
		local base = tcf:PointToWorldSpace(def.base)
		local L = K.Kagune.Length * def.len * gScale
		local restDir = tcf:VectorToWorldSpace(def.dir.Unit)
		local ph = def.phase
		-- Dururken yavaşça kıvrılan, yürürken arkada dalgalanan hareket
		local swayAmp = moving and 0.7 or 1.5
		local sway = tcf:VectorToWorldSpace(Vector3.new(
			math.sin(now * 1.3 + ph) * swayAmp,
			math.sin(now * 1.9 + ph * 1.3) * swayAmp * 0.8,
			math.cos(now * 1.1 + ph) * swayAmp * 0.6
		)) * gScale
		local tip = base + restDir * L + sway + trail
		local mid = base + restDir * L * 0.4 + sway * 0.35 + tcf:VectorToWorldSpace(Vector3.new(0, 1.6, 1.4)) * gScale

		if action then
			local amt = actionAmount(action, now)
			if amt > 0 then
				local goal = actionGoal(action, i, now, root, base)
				local side = tcf.RightVector * (((i - 1) % 2) * 2 - 1) * 2.5
				local goalMid = base:Lerp(goal, 0.45) + Vector3.new(0, 3, 0) + side
				tip = tip:Lerp(goal, amt)
				mid = mid:Lerp(goalMid, amt)
			end
		end

		local prev = base
		for s = 1, n do
			local t = s / n
			local p = bezier(base, mid, tip, t)
			-- dalga: dokunaç boyunca küçük kıvrımlar
			local wiggle = tcf:VectorToWorldSpace(Vector3.new(math.sin(now * 4 + t * 8 + ph), math.cos(now * 3.3 + t * 7 + ph), 0)) * 0.18 * t * gScale
			p += wiggle
			local w = (K.Kagune.BaseWidth + (K.Kagune.TipWidth - K.Kagune.BaseWidth) * t) * math.sqrt(math.max(g, 0.01))
			local seg = tent.segs[s]
			local joint = tent.joints[s]
			local len = (p - prev).Magnitude
			if len > 0.001 then
				seg.Size = Vector3.new(len * 1.15, w, w)
				seg.CFrame = CFrame.lookAt((prev + p) / 2, p) * CFrame.Angles(0, math.rad(90), 0)
			end
			joint.Size = Vector3.one * w * 1.08
			joint.CFrame = CFrame.new(p)
			prev = p
		end
	end
	r.light.Brightness = 2 * g

	-- Kakugan
	if head and g > 0.2 then
		local hs = head.Size
		local eyeCF = head.CFrame * CFrame.new(-hs.X * 0.16, hs.Y * 0.08, -hs.Z / 2 - 0.02)
		r.sclera.Size = Vector3.new(hs.X * 0.2, hs.Y * 0.11, 0.03)
		r.sclera.CFrame = eyeCF
		r.iris.Size = Vector3.new(hs.X * 0.08, hs.Y * 0.08, 0.03)
		r.iris.CFrame = eyeCF * CFrame.new(0, 0, -0.012)
		r.sclera.Transparency = 0
		r.iris.Transparency = 0
	else
		r.sclera.Transparency = 1
		r.iris.Transparency = 1
	end
end

RunService.RenderStepped:Connect(function(dt)
	local now = os.clock()
	for _, plr in ipairs(Players:GetPlayers()) do
		local char = plr.Character
		if char and char:GetAttribute("KaguneOut") and not renders[char] then
			createRender(char)
		end
	end
	for char, r in pairs(renders) do
		updateRender(r, dt, now)
	end
	if isKaneki() then
		refreshHUD()
	end
end)

---------------------------------------------------------------------
-- Sunucudan gelen efektler
---------------------------------------------------------------------
local function myRoot()
	local char = player.Character
	return char and char:FindFirstChild("HumanoidRootPart")
end

fxRemote.OnClientEvent:Connect(function(kind, a, b, c)
	if kind == "Cooldown" then
		local s = slots[a]
		if s then
			s.cd.Size = UDim2.fromScale(1, 1)
			tween(s.cd, b, { Size = UDim2.fromScale(1, 0) }, Enum.EasingStyle.Linear)
		end
	elseif kind == "Shake" then
		local root = myRoot()
		local dist = root and (root.Position - a).Magnitude or math.huge
		local falloff = math.clamp(1 - dist / 100, 0, 1)
		if falloff > 0 then
			shakePower = b * falloff
			shakeUntil = os.clock() + c
		end
	elseif kind == "Strike" or kind == "Flurry" or kind == "Grab" then
		local char = a
		local r = char and (renders[char] or (char:GetAttribute("KaguneOut") and createRender(char)))
		if r then
			local dur = (kind == "Flurry") and b or c
			r.action = { kind = kind, start = os.clock(), dur = dur, target = (kind ~= "Flurry") and b or nil }
		end
	end
end)

---------------------------------------------------------------------
-- Girdi
---------------------------------------------------------------------
local keyToAbility = {
	[K.Keys.Kagune] = "Kagune",
	[K.Keys.Strike] = "Strike",
	[K.Keys.Flurry] = "Flurry",
	[K.Keys.Grab] = "Grab",
}

UserInputService.InputBegan:Connect(function(input, processed)
	if processed or not isKaneki() then
		return
	end
	local ability = keyToAbility[input.KeyCode]
	if ability then
		abilityRemote:FireServer(ability, camera.CFrame.LookVector)
	end
end)

refreshHUD()
print("[Kaneki] KanekiClient hazır")
