-- KanekiServer (Script) -> ServerScriptService
-- Kaneki: parmak kütletme animasyonu, kagune aç/kapa, saldırılar ve hasar.
-- Kagune dokunaçlarının kendisi her oyuncunun ekranında (KanekiClient) çizilir; burası mantığı yönetir.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Debris = game:GetService("Debris")

print("[Kaneki] KanekiServer başladı")
local K = require(ReplicatedStorage:WaitForChild("KanekiConfig"))
local RigPose = require(ReplicatedStorage:WaitForChild("RigPose"))

local remotes = Instance.new("Folder")
remotes.Name = "KanekiRemotes"
remotes.Parent = ReplicatedStorage
local abilityRemote = Instance.new("RemoteEvent")
abilityRemote.Name = "Ability"
abilityRemote.Parent = remotes
local fxRemote = Instance.new("RemoteEvent")
fxRemote.Name = "Fx"
fxRemote.Parent = remotes

local fxFolder = Instance.new("Folder")
fxFolder.Name = "KanekiFx"
fxFolder.Parent = workspace

local states = {}
local function getState(player)
	local s = states[player]
	if not s then
		s = { busy = false, cooldowns = {}, idle = 0, baseSpeed = 16 }
		states[player] = s
	end
	return s
end

local function isKaneki(player)
	return player:GetAttribute("SelectedCharacter") == "Kaneki"
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

local function playSound(key, parent)
	local cfg = K.Sounds[key]
	if not cfg or not parent then
		return
	end
	local snd = Instance.new("Sound")
	snd.SoundId = cfg.Id
	snd.Volume = cfg.Volume or 1
	snd.PlaybackSpeed = cfg.Speed or 1
	snd.RollOffMaxDistance = 200
	snd.Parent = parent
	snd:Play()
	Debris:AddItem(snd, 8)
end

local function hitBurst(pos)
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
	e.Texture = "rbxasset://textures/particles/sparkles_main.dds"
	e.Color = ColorSequence.new(K.Kagune.TipColor, K.Kagune.BaseColor)
	e.LightEmission = 0.6
	e.Size = NumberSequence.new(0.5, 0)
	e.Speed = NumberRange.new(10, 22)
	e.SpreadAngle = Vector2.new(180, 180)
	e.Lifetime = NumberRange.new(0.25, 0.5)
	e.Rate = 0
	e.Parent = p
	e:Emit(25)
	Debris:AddItem(p, 1)
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
		if model and not found[model] and hum.Health > 0 then
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

local function damage(t, amount, knockDir, knockPower)
	t.hum:TakeDamage(amount)
	hitBurst(t.root.Position)
	playSound("Hit", t.root)
	if knockDir and knockPower and t.root:IsA("BasePart") and not t.root.Anchored then
		t.root.AssemblyLinearVelocity = knockDir * knockPower + Vector3.new(0, knockPower * 0.35, 0)
	end
end

---------------------------------------------------------------------
-- Parmak kütletme animasyonu (Kaneki'nin klasik hareketi)
---------------------------------------------------------------------
local function crackFingers(char, root)
	-- Sağ el göğüs hizasına gelir, kafa ele bakar
	RigPose.set(char, {
		RightShoulder = CFrame.Angles(math.rad(70), 0, math.rad(-35)),
		RightElbow = CFrame.Angles(math.rad(100), 0, 0),
		RightWrist = CFrame.Angles(math.rad(-10), 0, 0),
		LeftShoulder = CFrame.Angles(math.rad(10), 0, 0),
		Neck = CFrame.Angles(math.rad(-20), math.rad(-10), 0),
	}, 0.35, Enum.EasingStyle.Quad)
	task.wait(0.45)
	-- Başparmakla işaret parmağını kütletir: bilek kısa sert hareketler
	local hand = char:FindFirstChild("RightHand") or root
	for _ = 1, 3 do
		RigPose.set(char, { RightWrist = CFrame.Angles(math.rad(35), 0, math.rad(8)) }, 0.05)
		playSound("Crack", hand)
		task.wait(0.09)
		RigPose.set(char, { RightWrist = CFrame.Angles(math.rad(-10), 0, 0) }, 0.08)
		task.wait(0.22)
	end
	task.wait(0.1)
end

local function setKagune(player, char, hum, root, state, on)
	if on then
		state.busy = true
		hum.WalkSpeed = 0 -- olduğu yerde animasyona girer
		crackFingers(char, root)
		if not char.Parent then
			return
		end
		-- Kagune patlayarak açılır
		RigPose.set(char, {
			RightShoulder = CFrame.Angles(math.rad(20), 0, math.rad(25)),
			LeftShoulder = CFrame.Angles(math.rad(20), 0, math.rad(-25)),
			Waist = CFrame.Angles(math.rad(-15), 0, 0),
			Neck = CFrame.Angles(math.rad(10), 0, 0),
			RightElbow = CFrame.Angles(math.rad(30), 0, 0),
			LeftElbow = CFrame.Angles(math.rad(30), 0, 0),
		}, 0.15, Enum.EasingStyle.Back)
		char:SetAttribute("KaguneOut", true)
		playSound("KaguneOut", root)
		hitBurst(root.Position + root.CFrame.LookVector * -1)
		fxRemote:FireAllClients("Shake", root.Position, 0.7, 0.5)
		task.wait(0.6)
		RigPose.reset(char, 0.4)
		hum.WalkSpeed = K.WalkSpeed
		state.busy = false
	else
		char:SetAttribute("KaguneOut", false)
		playSound("KaguneIn", root)
		hum.WalkSpeed = state.baseSpeed
	end
end

---------------------------------------------------------------------
-- Saldırılar
---------------------------------------------------------------------
local function doStrike(char, root, dir)
	local cfg = K.Strike
	local targets = {}
	for _, t in ipairs(findTargets(char, root.Position, cfg.Range)) do
		if inCone(root.Position, dir, t.root.Position, cfg.ConeAngle) then
			table.insert(targets, t)
		end
	end
	local aim = targets[1] and targets[1].root.Position or (root.Position + dir * cfg.Range * 0.8)
	fxRemote:FireAllClients("Strike", char, aim, 0.55)
	playSound("Strike", root)
	RigPose.set(char, { Waist = CFrame.Angles(math.rad(-12), 0, 0), RightShoulder = CFrame.Angles(math.rad(40), 0, 0) }, 0.1)
	task.delay(0.55, function()
		RigPose.reset(char, 0.3)
	end)
	task.delay(0.15, function()
		for _, t in ipairs(targets) do
			damage(t, cfg.Damage, dir, cfg.Knockback)
		end
	end)
end

local function doFlurry(char, root)
	local cfg = K.Flurry
	local duration = cfg.Hits * cfg.Interval + 0.3
	fxRemote:FireAllClients("Flurry", char, duration)
	RigPose.set(char, {
		RightShoulder = CFrame.Angles(0, 0, math.rad(35)),
		LeftShoulder = CFrame.Angles(0, 0, math.rad(-35)),
		Waist = CFrame.Angles(math.rad(-8), 0, 0),
	}, 0.2)
	for _ = 1, cfg.Hits do
		if not root.Parent then
			break
		end
		playSound("Flurry", root)
		for _, t in ipairs(findTargets(char, root.Position, cfg.Radius)) do
			local away = t.root.Position - root.Position
			away = away.Magnitude > 0.1 and away.Unit or root.CFrame.LookVector
			damage(t, cfg.Damage, away, 12)
		end
		task.wait(cfg.Interval)
	end
	RigPose.reset(char, 0.3)
end

local function doGrab(char, root, dir)
	local cfg = K.Grab
	local target
	for _, t in ipairs(findTargets(char, root.Position, cfg.Range)) do
		if inCone(root.Position, dir, t.root.Position, cfg.ConeAngle) then
			target = t
			break
		end
	end
	if not target or not target.root:IsA("BasePart") then
		-- Boşa uzanır
		fxRemote:FireAllClients("Strike", char, root.Position + dir * cfg.Range * 0.7, 0.5)
		playSound("Strike", root)
		return
	end

	local troot = target.root
	fxRemote:FireAllClients("Grab", char, troot, 1.5)
	playSound("Strike", root)
	RigPose.set(char, { RightShoulder = CFrame.Angles(math.rad(80), 0, 0), Waist = CFrame.Angles(math.rad(-10), 0, 0) }, 0.15)

	local wasAnchored = troot.Anchored
	troot.Anchored = true
	task.wait(0.2)
	-- Havaya kaldır
	local liftCF = CFrame.new(root.Position + dir * 7 + Vector3.new(0, cfg.LiftHeight, 0))
	tween(troot, 0.5, { CFrame = liftCF }, Enum.EasingStyle.Back)
	playSound("Hit", troot)
	task.wait(0.75)
	-- Yere çarp
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { char, target.model, fxFolder }
	local hit = workspace:Raycast(liftCF.Position, Vector3.new(0, -60, 0), params)
	local groundY = hit and hit.Position.Y + 3 or (root.Position.Y)
	local slamPos = Vector3.new(liftCF.Position.X, groundY, liftCF.Position.Z)
	RigPose.set(char, { RightShoulder = CFrame.Angles(math.rad(-20), 0, 0), Waist = CFrame.Angles(math.rad(-20), 0, 0) }, 0.12)
	tween(troot, 0.15, { CFrame = CFrame.new(slamPos) }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
	task.wait(0.15)
	if target.model.Parent then
		damage(target, cfg.Damage)
		playSound("Slam", troot)
		fxRemote:FireAllClients("Shake", slamPos, 1, 0.5)
	end
	if troot.Parent and not wasAnchored then
		troot.Anchored = false
	end
	task.wait(0.2)
	RigPose.reset(char, 0.35)
end

---------------------------------------------------------------------
-- İstekler
---------------------------------------------------------------------
abilityRemote.OnServerEvent:Connect(function(player, ability, aimDir)
	if not isKaneki(player) then
		return
	end
	local char, hum, root = getAlive(player)
	if not char then
		return
	end
	local state = getState(player)
	if state.busy or typeof(ability) ~= "string" then
		return
	end
	local cd = K.Cooldowns[ability]
	if not cd then
		return
	end
	local now = os.clock()
	if (state.cooldowns[ability] or 0) > now then
		return
	end
	local kaguneOut = char:GetAttribute("KaguneOut") == true
	if ability ~= "Kagune" and not kaguneOut then
		return -- saldırılar için önce kagune açılmalı
	end

	local dir = root.CFrame.LookVector
	if typeof(aimDir) == "Vector3" and aimDir.Magnitude > 0.01 and aimDir.Magnitude < 2 then
		dir = aimDir.Unit
	end

	state.cooldowns[ability] = now + cd
	state.idle = 0
	fxRemote:FireClient(player, "Cooldown", ability, cd)

	task.spawn(function()
		local ok, err = pcall(function()
			if ability == "Kagune" then
				setKagune(player, char, hum, root, state, not kaguneOut)
			elseif ability == "Strike" then
				doStrike(char, root, dir)
			else
				state.busy = true
				if ability == "Flurry" then
					doFlurry(char, root)
				elseif ability == "Grab" then
					doGrab(char, root, dir)
				end
			end
		end)
		if not ok then
			warn("[Kaneki] Skill hatası:", err)
			if hum.Parent and hum.Health > 0 then
				hum.WalkSpeed = kaguneOut and K.WalkSpeed or state.baseSpeed
			end
		end
		if ability ~= "Strike" then
			state.busy = false
		end
	end)
end)

-- Dururken ara sıra kendiliğinden parmak kütletme (idle animasyonu)
task.spawn(function()
	while true do
		task.wait(1)
		for _, player in ipairs(Players:GetPlayers()) do
			if isKaneki(player) then
				local char, hum, root = getAlive(player)
				local state = getState(player)
				if char and char:GetAttribute("KaguneOut") and not state.busy and hum.MoveDirection.Magnitude < 0.1 then
					state.idle += 1
					if state.idle >= K.IdleCrackAfter then
						state.idle = 0
						state.busy = true
						task.spawn(function()
							pcall(function()
								crackFingers(char, root)
								RigPose.reset(char, 0.35)
							end)
							state.busy = false
						end)
					end
				else
					state.idle = 0
				end
			end
		end
	end
end)

Players.PlayerAdded:Connect(function(player)
	player.CharacterAdded:Connect(function(char)
		local state = getState(player)
		state.busy = false
		state.idle = 0
		local hum = char:WaitForChild("Humanoid")
		state.baseSpeed = hum.WalkSpeed
		char:SetAttribute("KaguneOut", false)
	end)
end)

Players.PlayerRemoving:Connect(function(player)
	states[player] = nil
end)

print("[Kaneki] KanekiServer hazır")
