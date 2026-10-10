-- VoidServer (Script) -> ServerScriptService
-- Void karakterinin sunucu tarafı: skill doğrulama, cooldown, hasar, gölge ölüm efekti,
-- Void formu (simsiyah beden + beyaz gözler) ve ultimate cutscene akışı.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Debris = game:GetService("Debris")

print("[Void] VoidServer başladı")
local configModule = ReplicatedStorage:WaitForChild("VoidConfig", 5)
if not configModule or not configModule:IsA("ModuleScript") then
	error("[Void] ReplicatedStorage içinde 'VoidConfig' adında bir ModuleScript bulunamadı! (Script değil, ModuleScript olmalı)")
end
local Config = require(configModule)

local SMOKE_TEXTURE = "rbxasset://textures/particles/smoke_main.dds"

-- Remote'lar
local remotes = Instance.new("Folder")
remotes.Name = "VoidRemotes"
remotes.Parent = ReplicatedStorage

local abilityRemote = Instance.new("RemoteEvent")
abilityRemote.Name = "Ability"
abilityRemote.Parent = remotes

local cutsceneRemote = Instance.new("RemoteEvent")
cutsceneRemote.Name = "Cutscene"
cutsceneRemote.Parent = remotes

local fxRemote = Instance.new("RemoteEvent")
fxRemote.Name = "Fx"
fxRemote.Parent = remotes

local fxFolder = Instance.new("Folder")
fxFolder.Name = "VoidFx"
fxFolder.Parent = workspace

local states = {} -- [player] = { voidForm, busy, cooldowns, eyes }

local function getState(player)
	local s = states[player]
	if not s then
		s = { voidForm = false, busy = false, cooldowns = {}, eyes = nil }
		states[player] = s
	end
	return s
end

local function getAlive(player)
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	local root = char and char:FindFirstChild("HumanoidRootPart")
	if hum and root and hum.Health > 0 then
		return char, hum, root
	end
	return nil
end

local function tween(obj, time, props, style, dir)
	local t = TweenService:Create(obj, TweenInfo.new(time, style or Enum.EasingStyle.Quad, dir or Enum.EasingDirection.Out), props)
	t:Play()
	return t
end

local function makeSmoke(parent, rate, sizeA, sizeB, lifetime, speed)
	local e = Instance.new("ParticleEmitter")
	e.Texture = SMOKE_TEXTURE
	e.Color = ColorSequence.new(Config.ShadowColor)
	e.LightEmission = 0
	e.LightInfluence = 0
	e.Rate = rate
	e.Lifetime = NumberRange.new(lifetime * 0.6, lifetime)
	e.Speed = NumberRange.new(speed * 0.4, speed)
	e.SpreadAngle = Vector2.new(180, 180)
	e.Rotation = NumberRange.new(0, 360)
	e.RotSpeed = NumberRange.new(-40, 40)
	e.Acceleration = Vector3.new(0, 2, 0)
	e.Size = NumberSequence.new({
		NumberSequenceKeypoint.new(0, sizeA),
		NumberSequenceKeypoint.new(1, sizeB),
	})
	e.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.25),
		NumberSequenceKeypoint.new(0.6, 0.55),
		NumberSequenceKeypoint.new(1, 1),
	})
	e.Parent = parent
	return e
end

local function fxPart(props)
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Material = Enum.Material.SmoothPlastic
	p.Color = Config.ShadowColor
	for k, v in pairs(props) do
		p[k] = v
	end
	p.Parent = fxFolder
	return p
end

---------------------------------------------------------------------
-- Kol pozları — Motor6D (C0) ve yeni AnimationConstraint eklemleri desteklenir
---------------------------------------------------------------------
local RunService = game:GetService("RunService")
local originalCF = setmetatable({}, { __mode = "k" })
local activeLerp = setmetatable({}, { __mode = "k" })

local function getShoulders(char)
	local rua = char:FindFirstChild("RightUpperArm")
	local lua = char:FindFirstChild("LeftUpperArm")
	if rua and lua then
		return rua:FindFirstChild("RightShoulder"), lua:FindFirstChild("LeftShoulder"), "R15"
	end
	local torso = char:FindFirstChild("Torso")
	if torso then
		return torso:FindFirstChild("Right Shoulder"), torso:FindFirstChild("Left Shoulder"), "R6"
	end
	return nil
end

-- Eklemin döndürülebilir kısmını bul: Motor6D -> C0, AnimationConstraint -> Attachment0.CFrame
local function jointHandle(joint)
	if not joint then
		return nil
	end
	if joint:IsA("Motor6D") or joint:IsA("Weld") then
		local ok = pcall(function()
			joint.C0 = joint.C0
		end)
		if ok then
			return joint, "C0"
		end
	end
	local ok, att = pcall(function()
		return joint.Attachment0
	end)
	if ok and att then
		return att, "CFrame"
	end
	return nil
end

local function lerpCFrame(obj, prop, target, time, style)
	local start = obj[prop]
	local token = {}
	activeLerp[obj] = token
	local t0 = os.clock()
	local conn
	conn = RunService.Heartbeat:Connect(function()
		if activeLerp[obj] ~= token or not obj.Parent then
			conn:Disconnect()
			return
		end
		local a = math.clamp((os.clock() - t0) / time, 0, 1)
		local e = TweenService:GetValue(a, style, Enum.EasingDirection.Out)
		pcall(function()
			obj[prop] = start:Lerp(target, e)
		end)
		if a >= 1 then
			conn:Disconnect()
		end
	end)
end

local function poseArms(char, pose, time)
	local ok, err = pcall(function()
		local rJoint, lJoint, rig = getShoulders(char)
		local rObj, rProp = jointHandle(rJoint)
		local lObj, lProp = jointHandle(lJoint)
		if not (rObj and lObj) then
			return
		end
		originalCF[rObj] = originalCF[rObj] or rObj[rProp]
		originalCF[lObj] = originalCF[lObj] or lObj[lProp]
		local r0, l0 = originalCF[rObj], originalCF[lObj]
		local rT, lT = r0, l0

		if pose == "Open" then -- kolları iki yana aç
			if rig == "R15" then
				rT = r0 * CFrame.Angles(math.rad(15), 0, math.rad(80))
				lT = l0 * CFrame.Angles(math.rad(15), 0, math.rad(-80))
			else
				rT = r0 * CFrame.Angles(math.rad(-80), 0, 0)
				lT = l0 * CFrame.Angles(math.rad(-80), 0, 0)
			end
		elseif pose == "Reach" then -- sağ eli öne uzat
			if rig == "R15" then
				rT = r0 * CFrame.Angles(math.rad(90), 0, 0)
			else
				rT = r0 * CFrame.Angles(0, 0, math.rad(90))
			end
		end

		lerpCFrame(rObj, rProp, rT, time or 0.3, Enum.EasingStyle.Back)
		lerpCFrame(lObj, lProp, lT, time or 0.3, Enum.EasingStyle.Back)
	end)
	if not ok then
		warn("[Void] Kol pozu uygulanamadı:", err)
	end
end

---------------------------------------------------------------------
-- Sesler
---------------------------------------------------------------------
local function playSound(key, parent, idOverride)
	local cfg = Config.Sounds and Config.Sounds[key]
	local id = idOverride or (cfg and cfg.Id)
	if not id or id == "" or not parent then
		return nil
	end
	local snd = Instance.new("Sound")
	snd.SoundId = id
	snd.Volume = idOverride and 2 or (cfg and cfg.Volume or 1)
	snd.PlaybackSpeed = (not idOverride and cfg and cfg.Speed) or 1
	snd.Looped = (not idOverride and cfg and cfg.Looped) or false
	snd.RollOffMaxDistance = 250
	local reverb = Instance.new("ReverbSoundEffect")
	reverb.DecayTime = 2.5
	reverb.WetLevel = -4
	reverb.Parent = snd
	snd.Parent = parent
	snd:Play()
	if not snd.Looped then
		Debris:AddItem(snd, 12)
	end
	return snd
end

---------------------------------------------------------------------
-- Void formu: simsiyah beden, hafif beyaz gözler, gölge aurası
---------------------------------------------------------------------
local function clearVoidVisuals(char, state)
	if state.eyes then
		state.eyes:Destroy()
		state.eyes = nil
	end
	if char then
		for _, name in ipairs({ "VoidHighlight", "VoidAura", "VoidAura2" }) do
			local obj = char:FindFirstChild(name, true)
			while obj do
				obj:Destroy()
				obj = char:FindFirstChild(name, true)
			end
		end
	end
end

local function applyVoidVisuals(player, char, state)
	clearVoidVisuals(char, state)
	local head = char:FindFirstChild("Head")
	local root = char:FindFirstChild("HumanoidRootPart")
	if not (head and root) then
		return
	end

	-- Highlight ile tüm karakter (aksesuarlar dahil) simsiyah silüet olur
	local hl = Instance.new("Highlight")
	hl.Name = "VoidHighlight"
	hl.FillColor = Config.ShadowColor
	hl.FillTransparency = 1
	hl.OutlineColor = Color3.fromRGB(25, 25, 32)
	hl.OutlineTransparency = 1
	hl.DepthMode = Enum.HighlightDepthMode.Occluded
	hl.Parent = char
	tween(hl, 0.8, { FillTransparency = 0, OutlineTransparency = 0.5 })

	-- Gözler karakterin dışında bir klasörde (yoksa Highlight onları da siyah yapar)
	local eyes = Instance.new("Folder")
	eyes.Name = "VoidEyes_" .. player.Name
	eyes.Parent = fxFolder
	state.eyes = eyes

	local z = -head.Size.Z / 2 - 0.03
	for _, side in ipairs({ -1, 1 }) do
		local eye = Instance.new("Part")
		eye.Name = "Eye"
		eye.Size = Vector3.new(0.2, 0.08, 0.05)
		eye.Material = Enum.Material.Neon
		eye.Color = Config.EyeColor
		eye.Transparency = 1
		eye.CanCollide = false
		eye.CanQuery = false
		eye.CanTouch = false
		eye.Massless = true
		eye.CastShadow = false
		eye.CFrame = head.CFrame * CFrame.new(side * head.Size.X * 0.15, head.Size.Y * 0.08, z)
			* CFrame.Angles(0, 0, math.rad(side * -8)) -- hafif çekik, sert bakış
		local weld = Instance.new("WeldConstraint")
		weld.Part0 = head
		weld.Part1 = eye
		weld.Parent = eye
		local light = Instance.new("PointLight")
		light.Color = Config.EyeColor
		light.Range = 3
		light.Brightness = 0.6
		light.Parent = eye
		eye.Parent = eyes
		tween(eye, 1.2, { Transparency = 0.15 })
	end

	-- Gövdeden yükselen siyah duman
	local aura = makeSmoke(root, 18, 1.2, 4, 1.8, 2.5)
	aura.Name = "VoidAura"
	local torso = char:FindFirstChild("UpperTorso") or char:FindFirstChild("Torso")
	if torso then
		local aura2 = makeSmoke(torso, 10, 0.6, 2, 1.2, 1)
		aura2.Name = "VoidAura2"
	end

	-- Dönüşüm patlaması
	local burst = makeSmoke(root, 0, 2, 7, 1.4, 14)
	burst:Emit(45)
	Debris:AddItem(burst, 2)
	playSound("Transform", root)
	fxRemote:FireAllClients("Transform", char)
end

local function setVoidForm(player, on)
	local state = getState(player)
	local char = player.Character
	state.voidForm = on
	if on and char then
		applyVoidVisuals(player, char, state)
	else
		clearVoidVisuals(char, state)
	end
	player:SetAttribute("VoidForm", on)
end

---------------------------------------------------------------------
-- Hedef bulma
---------------------------------------------------------------------
local function findHumanoidModel(part)
	local model = part:FindFirstAncestorOfClass("Model")
	while model do
		local hum = model:FindFirstChildOfClass("Humanoid")
		if hum then
			return model, hum
		end
		model = model:FindFirstAncestorOfClass("Model")
	end
	return nil
end

local function findTargets(casterChar, origin, radius)
	local params = OverlapParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { casterChar, fxFolder }
	local found, list = {}, {}
	for _, part in ipairs(workspace:GetPartBoundsInRadius(origin, radius, params)) do
		local model, hum = findHumanoidModel(part)
		if model and not found[model] and hum.Health > 0 and not model:GetAttribute("VoidMarked") then
			local root = model:FindFirstChild("HumanoidRootPart") or model.PrimaryPart or part
			found[model] = true
			table.insert(list, { model = model, hum = hum, root = root, dist = (root.Position - origin).Magnitude })
		end
	end
	table.sort(list, function(a, b)
		return a.dist < b.dist
	end)
	return list
end

local function inCone(origin, dir, pos, angleDeg)
	local to = pos - origin
	if to.Magnitude < 0.1 then
		return true
	end
	return dir:Dot(to.Unit) >= math.cos(math.rad(angleDeg))
end

---------------------------------------------------------------------
-- Gölgeye dönüşüp duman olarak dağılma (ölüm efekti)
---------------------------------------------------------------------
local function shadowDissolve(model)
	if model:GetAttribute("VoidDissolving") then
		return
	end
	model:SetAttribute("VoidDissolving", true)
	playSound("Dissolve", model:FindFirstChild("HumanoidRootPart") or model:FindFirstChildWhichIsA("BasePart"))

	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("BasePart") then
			d.Anchored = true
			d.CanCollide = false
			local drift = Vector3.new(math.random() - 0.5, 1.2 + math.random(), math.random() - 0.5) * 3
			local smoke = makeSmoke(d, 0, 0.8, 3, 1.6, 3)
			smoke:Emit(8)
			tween(d, 1.8, { Transparency = 1, CFrame = d.CFrame + drift }, Enum.EasingStyle.Sine, Enum.EasingDirection.In)
		elseif d:IsA("Decal") or d:IsA("Texture") then
			tween(d, 1.2, { Transparency = 1 })
		end
	end
	if not Players:GetPlayerFromCharacter(model) then
		Debris:AddItem(model, 3)
	end
end

-- Hedefi siyah gölgeye çevirir, hasar verir; ölürse duman olup dağılır.
local function voidHit(target, damage, darkenTime)
	local model, hum = target.model, target.hum
	if model:GetAttribute("VoidMarked") then
		return
	end
	model:SetAttribute("VoidMarked", true)

	local hl = Instance.new("Highlight")
	hl.Name = "VoidTargetHighlight"
	hl.FillColor = Config.ShadowColor
	hl.OutlineColor = Config.ShadowColor
	hl.FillTransparency = 1
	hl.OutlineTransparency = 1
	hl.DepthMode = Enum.HighlightDepthMode.Occluded
	hl.Parent = model
	tween(hl, darkenTime, { FillTransparency = 0, OutlineTransparency = 0.3 })

	local smoke = makeSmoke(target.root, 25, 1, 3.5, 1.4, 2)
	task.delay(darkenTime, function()
		if not model.Parent then
			return
		end
		local willDie = hum.Health - damage <= 0
		if willDie then
			hum.BreakJointsOnDeath = false
		end
		hum:TakeDamage(damage)
		if hum.Health <= 0 then
			shadowDissolve(model)
		else
			-- hayatta kaldı: gölge yavaşça çekilsin
			model:SetAttribute("VoidMarked", nil)
			tween(hl, 0.8, { FillTransparency = 1, OutlineTransparency = 1 })
			Debris:AddItem(hl, 0.9)
			smoke.Enabled = false
			Debris:AddItem(smoke, 2)
			if target.unanchorOnSurvive and target.root.Parent then
				target.root.Anchored = false
			end
		end
	end)
end

---------------------------------------------------------------------
-- Skiller
---------------------------------------------------------------------
local function rightHandAttachment(char)
	local hand = char:FindFirstChild("RightHand") or char:FindFirstChild("Right Arm")
	if not hand then
		return nil
	end
	local att = Instance.new("Attachment")
	att.Position = Vector3.new(0, -hand.Size.Y / 2, 0)
	att.Parent = hand
	return att
end

local function doGrasp(player, char, root, dir)
	local cfg = Config.Grasp
	local target
	for _, t in ipairs(findTargets(char, root.Position, cfg.Range)) do
		if inCone(root.Position, dir, t.root.Position, cfg.ConeAngle) then
			target = t
			break
		end
	end

	poseArms(char, "Reach", 0.2)
	playSound("GraspCast", root)
	task.delay(1.4, function()
		poseArms(char, "Reset", 0.4)
	end)
	if not target then
		return
	end

	-- Elden hedefe uzanan gölge dokunaçları
	local a0 = rightHandAttachment(char)
	local a1 = Instance.new("Attachment")
	a1.Parent = target.root
	if a0 then
		for i = 1, 3 do
			local beam = Instance.new("Beam")
			beam.Attachment0 = a0
			beam.Attachment1 = a1
			beam.Color = ColorSequence.new(Config.ShadowColor)
			beam.LightEmission = 0
			beam.LightInfluence = 0
			beam.FaceCamera = true
			beam.Segments = 20
			beam.Width0 = 0.9 - i * 0.2
			beam.Width1 = 0.15
			beam.CurveSize0 = (math.random() - 0.5) * 8
			beam.CurveSize1 = (math.random() - 0.5) * 8
			beam.Transparency = NumberSequence.new(0.05)
			beam.Parent = a0
			Debris:AddItem(beam, 1.6)
		end
		Debris:AddItem(a0, 1.7)
	end
	Debris:AddItem(a1, 1.7)

	-- Hedefi havaya kaldırıp gölgeye çevir
	if target.root:IsA("BasePart") then
		target.unanchorOnSurvive = not target.root.Anchored
		target.root.Anchored = true
		tween(target.root, 1, { CFrame = target.root.CFrame + Vector3.new(0, 4, 0) }, Enum.EasingStyle.Sine)
	end
	playSound("GraspHit", target.root)
	fxRemote:FireAllClients("Shake", root.Position, 0.4, 0.5)
	voidHit(target, math.huge, 0.9)
end

local function doWave(player, char, root, dir)
	local cfg = Config.Wave
	poseArms(char, "Reach", 0.15)
	playSound("Wave", root)
	task.delay(1, function()
		poseArms(char, "Reset", 0.4)
	end)

	local flatDir = Vector3.new(dir.X, 0, dir.Z)
	flatDir = flatDir.Magnitude > 0.01 and flatDir.Unit or root.CFrame.LookVector

	-- Görsel: ileri doğru ilerleyen gölge patlamaları
	task.spawn(function()
		for i = 1, 8 do
			local pos = root.Position + dir * (i * cfg.Range / 8)
			local size = 4 + i * 1.6
			local ball = fxPart({ Shape = Enum.PartType.Ball, Size = Vector3.one * 2, CFrame = CFrame.new(pos), Transparency = 0.25 })
			tween(ball, 0.5, { Size = Vector3.one * size, Transparency = 1 })
			local smoke = makeSmoke(ball, 0, 2, size * 0.7, 1.2, 6)
			smoke:Emit(10)
			Debris:AddItem(ball, 1.5)
			task.wait(0.04)
		end
	end)
	fxRemote:FireAllClients("Shake", root.Position, 0.6, 0.4)

	for _, t in ipairs(findTargets(char, root.Position, cfg.Range)) do
		if inCone(root.Position, dir, t.root.Position, cfg.ConeAngle) then
			task.delay(t.dist / cfg.Range * 0.35, function()
				voidHit(t, cfg.Damage, 0.25)
			end)
		end
	end
end

local function showLine(head, text, duration)
	local gui = Instance.new("BillboardGui")
	gui.Size = UDim2.fromScale(10, 1.6)
	gui.StudsOffset = Vector3.new(0, 3.2, 0)
	gui.AlwaysOnTop = true
	gui.LightInfluence = 0
	gui.MaxDistance = 200
	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.Font = Enum.Font.Antique
	label.TextScaled = true
	label.TextColor3 = Color3.fromRGB(235, 240, 255)
	label.TextStrokeColor3 = Color3.new(0, 0, 0)
	label.TextStrokeTransparency = 0.2
	label.Text = text
	label.MaxVisibleGraphemes = 0
	label.Parent = gui
	gui.Parent = head
	tween(label, math.min(1.2, duration * 0.5), { MaxVisibleGraphemes = #text }, Enum.EasingStyle.Linear)
	task.delay(duration, function()
		tween(label, 0.4, { TextTransparency = 1, TextStrokeTransparency = 1 })
		Debris:AddItem(gui, 0.5)
	end)
end

local function ultimateSequence(player, char, hum, root, state, ctx)
	local cfg = Config.Ultimate
	local startTime = workspace:GetServerTimeNow()
	local startCF = root.CFrame
	local head = char:FindFirstChild("Head")

	-- Karakteri dondur, ölümsüz yap
	local ff = Instance.new("ForceField")
	ff.Visible = false
	ff.Parent = char
	ctx.ff = ff
	root.Anchored = true
	ctx.riseSound = playSound("UltRise", root)

	cutsceneRemote:FireAllClients(char, startTime, cfg)

	-- Replikler
	for i, line in ipairs(cfg.Lines) do
		local nextAt = cfg.Lines[i + 1] and cfg.Lines[i + 1].At or cfg.ImpactAt
		task.delay(line.At, function()
			if head and head.Parent then
				showLine(head, line.Text, nextAt - line.At - 0.2)
				playSound("UltLine", head)
				if line.SoundId and line.SoundId ~= "" then
					playSound("UltLine", head, line.SoundId)
				end
			end
		end)
	end

	-- Yavaşça havaya yüksel ve süzül
	local upCF = startCF + Vector3.new(0, cfg.RiseHeight, 0)
	tween(root, cfg.ArmsOpenAt + 0.8, { CFrame = upCF }, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut)
	local floatAura = makeSmoke(root, 40, 2, 6, 2.2, 4)
	ctx.floatAura = floatAura

	task.wait(cfg.ArmsOpenAt)
	poseArms(char, "Open", 1.2)
	task.wait(0.8)

	-- Havada hafif süzülme (aşağı yukarı)
	ctx.floating = true
	task.spawn(function()
		local floatStart = os.clock()
		while ctx.floating and root.Parent do
			local t = os.clock() - floatStart
			root.CFrame = upCF + Vector3.new(0, math.sin(t * 1.6) * 0.6, 0)
			task.wait()
		end
	end)

	task.wait(cfg.ImpactAt - cfg.ArmsOpenAt - 0.8)

	-- ETKİ: büyük gölge küresi + herkes gölgeye dönüşür
	local center = root.Position
	local sphere = fxPart({ Shape = Enum.PartType.Ball, Size = Vector3.one * 4, CFrame = CFrame.new(center), Transparency = 0.15 })
	tween(sphere, 1.4, { Size = Vector3.one * cfg.Radius * 2, Transparency = 1 }, Enum.EasingStyle.Quart)
	Debris:AddItem(sphere, 1.6)
	local ring = fxPart({
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(0.4, 6, 6),
		CFrame = CFrame.new(center.X, startCF.Position.Y - 2.5, center.Z) * CFrame.Angles(0, 0, math.rad(90)),
		Transparency = 0.2,
	})
	tween(ring, 1.6, { Size = Vector3.new(0.4, cfg.Radius * 2.2, cfg.Radius * 2.2), Transparency = 1 }, Enum.EasingStyle.Quart)
	Debris:AddItem(ring, 1.8)
	local burst = makeSmoke(sphere, 0, 4, 14, 2.5, 40)
	burst:Emit(120)
	playSound("UltImpact", root)
	fxRemote:FireAllClients("Shake", center, 1.4, 1.2)

	for _, t in ipairs(findTargets(char, center, cfg.Radius)) do
		task.delay(0.15 + t.dist / cfg.Radius * 1.0, function()
			voidHit(t, math.huge, 0.6)
		end)
	end

	task.wait(cfg.EndAt - cfg.ImpactAt - 0.8)
	ctx.floating = false
	poseArms(char, "Reset", 0.8)
	tween(root, 0.8, { CFrame = startCF }, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut)
	task.wait(0.8)
end

-- Ne olursa olsun karakter havada donmuş kalmasın
local function doUltimate(player, char, hum, root, state)
	state.busy = true
	local ctx = {}
	local ok, err = pcall(ultimateSequence, player, char, hum, root, state, ctx)
	if not ok then
		warn("[Void] Ultimate hatası:", err)
		poseArms(char, "Reset", 0.3)
	end
	ctx.floating = false
	if ctx.floatAura then
		ctx.floatAura.Enabled = false
		Debris:AddItem(ctx.floatAura, 3)
	end
	if ctx.riseSound then
		ctx.riseSound:Destroy()
	end
	if ctx.ff then
		ctx.ff:Destroy()
	end
	if root.Parent then
		root.Anchored = false
	end
	state.busy = false
end

---------------------------------------------------------------------
-- İstek işleme
---------------------------------------------------------------------
abilityRemote.OnServerEvent:Connect(function(player, ability, aimDir)
	local char, hum, root = getAlive(player)
	if not char then
		return
	end
	local state = getState(player)
	if state.busy or typeof(ability) ~= "string" then
		return
	end

	local cd = Config.Cooldowns[ability]
	if not cd then
		return
	end
	local now = os.clock()
	if (state.cooldowns[ability] or 0) > now then
		return
	end

	local dir = root.CFrame.LookVector
	if typeof(aimDir) == "Vector3" and aimDir.Magnitude > 0.01 and aimDir.Magnitude < 2 then
		dir = aimDir.Unit
	end

	if ability == "VoidForm" then
		state.cooldowns[ability] = now + cd
		setVoidForm(player, not state.voidForm)
	elseif ability == "Grasp" then
		state.cooldowns[ability] = now + cd
		doGrasp(player, char, root, dir)
	elseif ability == "Wave" then
		state.cooldowns[ability] = now + cd
		doWave(player, char, root, dir)
	elseif ability == "Ultimate" then
		if Config.Ultimate.RequiresVoidForm and not state.voidForm then
			return
		end
		state.cooldowns[ability] = now + cd
		task.spawn(doUltimate, player, char, hum, root, state)
	end
	fxRemote:FireClient(player, "Cooldown", ability, cd)
end)

Players.PlayerAdded:Connect(function(player)
	player.CharacterAdded:Connect(function(char)
		local state = getState(player)
		state.busy = false
		clearVoidVisuals(nil, state)
		state.voidForm = false
		player:SetAttribute("VoidForm", false)
		local hum = char:WaitForChild("Humanoid")
		hum.Died:Connect(function()
			clearVoidVisuals(nil, state)
		end)
	end)
end)

Players.PlayerRemoving:Connect(function(player)
	local s = states[player]
	if s then
		clearVoidVisuals(nil, s)
	end
	states[player] = nil
end)

print("[Void] VoidServer hazır")
