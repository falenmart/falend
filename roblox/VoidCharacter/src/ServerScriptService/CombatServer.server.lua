-- CombatServer (Script) -> ServerScriptService
-- Sol tık kombo: 4 vuruşluk düz vuruşlar (yumruk). Kaneki'de kagune açıksa dokunaçla savurur,
-- Sentry Void formundaysa vuruşlar gölge dumanı bırakır.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Debris = game:GetService("Debris")

print("[Combat] CombatServer başladı")
if not ReplicatedStorage:WaitForChild("RigPose", 5) then
	error("[Combat] ReplicatedStorage içinde 'RigPose' ModuleScript'i yok!")
end
local RigPose = require(ReplicatedStorage.RigPose)

local SETTINGS = {
	Cooldown = 0.32,     -- vuruşlar arası
	ComboReset = 1.0,    -- bu kadar vurmazsan kombo sıfırlanır
	FinisherCooldown = 0.9,
	Damage = 7,
	FinisherDamage = 14,
	Range = 5.5,
	KaguneDamage = 11,
	KaguneFinisherDamage = 20,
	KaguneRange = 10,
	Knockback = 45,
}

local SOUNDS = {
	Swing = { Id = "rbxasset://sounds/swoosh.wav", Volume = 0.8, Speed = 1.4 },
	Hit = { Id = "rbxasset://sounds/collide.wav", Volume = 0.9, Speed = 1.2 },
	Finisher = { Id = "rbxasset://sounds/collide.wav", Volume = 1.4, Speed = 0.7 },
}

local remote = Instance.new("RemoteEvent")
remote.Name = "CombatM1"
remote.Parent = ReplicatedStorage

local fxFolder = Instance.new("Folder")
fxFolder.Name = "CombatFx"
fxFolder.Parent = workspace

local states = {}

local function playSound(key, parent)
	local cfg = SOUNDS[key]
	if not parent then
		return
	end
	local snd = Instance.new("Sound")
	snd.SoundId = cfg.Id
	snd.Volume = cfg.Volume
	snd.PlaybackSpeed = cfg.Speed * (0.92 + math.random() * 0.16)
	snd.RollOffMaxDistance = 120
	snd.Parent = parent
	snd:Play()
	Debris:AddItem(snd, 4)
end

local function hitFx(pos, color, smoke)
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Transparency = 1
	p.Size = Vector3.one
	p.CFrame = CFrame.new(pos)
	p.Parent = fxFolder
	local e = Instance.new("ParticleEmitter")
	e.Texture = smoke and "rbxasset://textures/particles/smoke_main.dds" or "rbxasset://textures/particles/sparkles_main.dds"
	e.Color = ColorSequence.new(color)
	e.LightEmission = smoke and 0 or 0.7
	e.LightInfluence = smoke and 0 or 1
	e.Size = smoke and NumberSequence.new(1, 3) or NumberSequence.new(0.4, 0)
	e.Transparency = NumberSequence.new(smoke and 0.3 or 0, 1)
	e.Speed = NumberRange.new(smoke and 3 or 10, smoke and 8 or 18)
	e.SpreadAngle = Vector2.new(180, 180)
	e.Lifetime = NumberRange.new(0.25, smoke and 0.8 or 0.4)
	e.Rate = 0
	e.Parent = p
	e:Emit(smoke and 12 or 15)
	Debris:AddItem(p, 1.2)
end

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

-- Önündeki kutuda vurulacakları bul
local function hitbox(char, root, range)
	local params = OverlapParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { char, fxFolder }
	local cf = root.CFrame * CFrame.new(0, 0, -range / 2 - 0.5)
	local found, list = {}, {}
	for _, part in ipairs(workspace:GetPartBoundsInBox(cf, Vector3.new(range * 0.9, 6, range), params)) do
		local model, hum = findHumanoidModel(part)
		if model and not found[model] and hum.Health > 0 then
			found[model] = true
			table.insert(list, { model = model, hum = hum, root = model:FindFirstChild("HumanoidRootPart") or part })
		end
	end
	return list
end

-- Yumruk pozları (sağ-sol-sağ-son vuruş)
local PUNCH = {
	{ RightShoulder = CFrame.Angles(math.rad(90), 0, 0), Waist = CFrame.Angles(0, math.rad(20), 0) },
	{ LeftShoulder = CFrame.Angles(math.rad(90), 0, 0), Waist = CFrame.Angles(0, math.rad(-20), 0) },
	{ RightShoulder = CFrame.Angles(math.rad(70), 0, math.rad(30)), Waist = CFrame.Angles(0, math.rad(30), 0) },
	{ RightShoulder = CFrame.Angles(math.rad(160), 0, 0), Waist = CFrame.Angles(math.rad(-15), 0, 0) },
}

remote.OnServerEvent:Connect(function(player)
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	local root = char and char:FindFirstChild("HumanoidRootPart")
	if not (hum and root) or hum.Health <= 0 or root.Anchored then
		return
	end
	local s = states[player]
	if not s then
		s = { last = 0, combo = 0, nextAllowed = 0 }
		states[player] = s
	end
	local now = os.clock()
	if now < s.nextAllowed then
		return
	end
	if now - s.last > SETTINGS.ComboReset then
		s.combo = 0
	end
	s.combo = s.combo % 4 + 1
	s.last = now
	local finisher = s.combo == 4
	s.nextAllowed = now + (finisher and SETTINGS.FinisherCooldown or SETTINGS.Cooldown)

	local selected = player:GetAttribute("SelectedCharacter")
	local kagune = selected == "Kaneki" and char:GetAttribute("KaguneOut") == true
	local voidForm = selected == "Sentry" and player:GetAttribute("VoidForm") == true

	playSound("Swing", root)
	if kagune then
		-- Kaneki: dokunaçla savurma (görseli KanekiClient çizer)
		local kr = ReplicatedStorage:FindFirstChild("KanekiRemotes")
		local fx = kr and kr:FindFirstChild("Fx")
		if fx then
			fx:FireAllClients("Swipe", char, s.combo)
		end
	else
		local pose = PUNCH[s.combo]
		RigPose.set(char, pose, 0.07, Enum.EasingStyle.Quad)
		task.delay(finisher and 0.35 or 0.2, function()
			if char.Parent then
				local reset = {}
				for k in pairs(pose) do
					reset[k] = CFrame.identity
				end
				RigPose.set(char, reset, 0.15)
			end
		end)
	end

	local range = kagune and SETTINGS.KaguneRange or SETTINGS.Range
	local dmg
	if kagune then
		dmg = finisher and SETTINGS.KaguneFinisherDamage or SETTINGS.KaguneDamage
	else
		dmg = finisher and SETTINGS.FinisherDamage or SETTINGS.Damage
	end

	task.delay(0.08, function()
		if not root.Parent then
			return
		end
		for _, t in ipairs(hitbox(char, root, range)) do
			t.hum:TakeDamage(dmg)
			local pos = t.root.Position
			if kagune then
				hitFx(pos, Color3.fromRGB(220, 20, 35), false)
			elseif voidForm then
				hitFx(pos, Color3.fromRGB(5, 5, 8), true)
			else
				hitFx(pos, Color3.fromRGB(255, 240, 200), false)
			end
			playSound(finisher and "Finisher" or "Hit", t.root)
			if t.root:IsA("BasePart") and not t.root.Anchored then
				local dir = (pos - root.Position) * Vector3.new(1, 0, 1)
				dir = dir.Magnitude > 0.1 and dir.Unit or root.CFrame.LookVector
				local power = finisher and SETTINGS.Knockback or 6
				t.root.AssemblyLinearVelocity = dir * power + Vector3.new(0, finisher and 20 or 0, 0)
			end
		end
	end)
end)

Players.PlayerRemoving:Connect(function(player)
	states[player] = nil
end)

print("[Combat] CombatServer hazır")
