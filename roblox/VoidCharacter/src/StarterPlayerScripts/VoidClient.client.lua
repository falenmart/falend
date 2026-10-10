-- VoidClient (LocalScript) -> StarterPlayer > StarterPlayerScripts
-- Girdi, uçuş, skill HUD'u, kamera sarsıntısı ve ultimate cutscene kamerası.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Lighting = game:GetService("Lighting")

print("[Void] VoidClient başladı")
local configModule = ReplicatedStorage:WaitForChild("VoidConfig", 5)
if not configModule or not configModule:IsA("ModuleScript") then
	error("[Void] ReplicatedStorage içinde 'VoidConfig' adında bir ModuleScript bulunamadı!")
end
local Config = require(configModule)
local remotes = ReplicatedStorage:WaitForChild("VoidRemotes", 10)
if not remotes then
	error("[Void] VoidRemotes yok -> VoidServer çalışmıyor. ServerScriptService içinde 'Script' olarak durduğundan emin ol.")
end
local abilityRemote = remotes:WaitForChild("Ability")
local cutsceneRemote = remotes:WaitForChild("Cutscene")
local fxRemote = remotes:WaitForChild("Fx")

local player = Players.LocalPlayer
local camera = workspace.CurrentCamera
-- Hareket girdisi: varsa Roblox PlayerModule, yoksa WASD'yi kendimiz okuruz
local controls
do
	local playerModule = player:WaitForChild("PlayerScripts"):WaitForChild("PlayerModule", 3)
	if playerModule then
		local ok, result = pcall(function()
			return require(playerModule):GetControls()
		end)
		if ok then
			controls = result
		end
	end
end

local function getMoveVector()
	if controls then
		local ok, mv = pcall(controls.GetMoveVector, controls)
		if ok and mv then
			return mv
		end
	end
	local x, z = 0, 0
	if UserInputService:IsKeyDown(Enum.KeyCode.W) or UserInputService:IsKeyDown(Enum.KeyCode.Up) then
		z -= 1
	end
	if UserInputService:IsKeyDown(Enum.KeyCode.S) or UserInputService:IsKeyDown(Enum.KeyCode.Down) then
		z += 1
	end
	if UserInputService:IsKeyDown(Enum.KeyCode.A) or UserInputService:IsKeyDown(Enum.KeyCode.Left) then
		x -= 1
	end
	if UserInputService:IsKeyDown(Enum.KeyCode.D) or UserInputService:IsKeyDown(Enum.KeyCode.Right) then
		x += 1
	end
	return Vector3.new(x, 0, z)
end

local inCutscene = false

local function tween(obj, time, props, style, dir)
	local t = TweenService:Create(obj, TweenInfo.new(time, style or Enum.EasingStyle.Quad, dir or Enum.EasingDirection.Out), props)
	t:Play()
	return t
end

---------------------------------------------------------------------
-- HUD
---------------------------------------------------------------------
local gui = Instance.new("ScreenGui")
gui.Name = "VoidHUD"
gui.ResetOnSpawn = false
gui.IgnoreGuiInset = true
gui.Parent = player:WaitForChild("PlayerGui")

local bar = Instance.new("Frame")
bar.AnchorPoint = Vector2.new(0.5, 1)
bar.Position = UDim2.new(0.5, 0, 1, -20)
bar.Size = UDim2.fromOffset(5 * 74, 64)
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
	f.BackgroundColor3 = Color3.fromRGB(10, 10, 14)
	f.BackgroundTransparency = 0.2
	f.ClipsDescendants = true
	f.Parent = bar
	Instance.new("UICorner", f).CornerRadius = UDim.new(0, 10)
	local stroke = Instance.new("UIStroke", f)
	stroke.Color = Color3.fromRGB(200, 210, 230)
	stroke.Transparency = 0.7
	local cd = Instance.new("Frame")
	cd.Name = "CD"
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
	k.TextColor3 = Color3.fromRGB(235, 240, 255)
	k.Text = key
	k.Parent = f
	local t = Instance.new("TextLabel")
	t.BackgroundTransparency = 1
	t.Position = UDim2.fromScale(0, 0.58)
	t.Size = UDim2.new(1, 0, 0.32, 0)
	t.Font = Enum.Font.GothamBold
	t.TextScaled = true
	t.TextColor3 = Color3.fromRGB(150, 155, 170)
	t.Text = title
	t.Parent = f
	slots[id] = { frame = f, cd = cd, stroke = stroke }
end

makeSlot(1, "Fly", Config.Keys.Fly.Name, "Uç")
makeSlot(2, "VoidForm", Config.Keys.VoidForm.Name, "Void")
makeSlot(3, "Grasp", Config.Keys.Grasp.Name, "Kavrayış")
makeSlot(4, "Wave", Config.Keys.Wave.Name, "Dalga")
makeSlot(5, "Ultimate", Config.Keys.Ultimate.Name, "Boşluk")

local function setActive(id, on)
	local s = slots[id]
	if s then
		tween(s.stroke, 0.2, { Transparency = on and 0 or 0.7, Thickness = on and 2 or 1 })
	end
end

local function startCooldown(id, seconds)
	local s = slots[id]
	if not s then
		return
	end
	s.cd.Size = UDim2.fromScale(1, 1)
	tween(s.cd, seconds, { Size = UDim2.fromScale(1, 0) }, Enum.EasingStyle.Linear)
end

player:GetAttributeChangedSignal("VoidForm"):Connect(function()
	setActive("VoidForm", player:GetAttribute("VoidForm") == true)
end)

---------------------------------------------------------------------
-- Uçuş
---------------------------------------------------------------------
local flying = false
local flyConn, linVel, alignOri, flyAtt

local function stopFlying()
	if not flying then
		return
	end
	flying = false
	if flyConn then
		flyConn:Disconnect()
		flyConn = nil
	end
	for _, obj in ipairs({ linVel, alignOri, flyAtt }) do
		if obj then
			obj:Destroy()
		end
	end
	linVel, alignOri, flyAtt = nil, nil, nil
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if hum then
		hum.PlatformStand = false
		hum:ChangeState(Enum.HumanoidStateType.Freefall)
	end
	setActive("Fly", false)
end

local function startFlying()
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	local root = char and char:FindFirstChild("HumanoidRootPart")
	if not (hum and root) or hum.Health <= 0 or root.Anchored then
		return
	end
	flying = true
	setActive("Fly", true)
	hum.PlatformStand = true

	flyAtt = Instance.new("Attachment")
	flyAtt.Name = "VoidFlyAttachment"
	flyAtt.Parent = root

	linVel = Instance.new("LinearVelocity")
	linVel.Attachment0 = flyAtt
	linVel.RelativeTo = Enum.ActuatorRelativeTo.World
	linVel.VelocityConstraintMode = Enum.VelocityConstraintMode.Vector
	linVel.MaxForce = math.huge
	linVel.VectorVelocity = Vector3.zero
	linVel.Parent = root

	alignOri = Instance.new("AlignOrientation")
	alignOri.Mode = Enum.OrientationAlignmentMode.OneAttachment
	alignOri.Attachment0 = flyAtt
	alignOri.MaxTorque = math.huge
	alignOri.Responsiveness = 18
	alignOri.CFrame = root.CFrame.Rotation
	alignOri.Parent = root

	local velocity = Vector3.zero
	local t = 0
	flyConn = RunService.Heartbeat:Connect(function(dt)
		if not root.Parent or hum.Health <= 0 then
			stopFlying()
			return
		end
		t += dt
		local mv = getMoveVector()
		local camCF = camera.CFrame
		local dir = camCF:VectorToWorldSpace(Vector3.new(mv.X, 0, mv.Z))
		local vertical = 0
		if UserInputService:IsKeyDown(Config.Keys.FlyUp) then
			vertical += 1
		end
		if UserInputService:IsKeyDown(Config.Keys.FlyDown) then
			vertical -= 1
		end
		dir += Vector3.new(0, vertical, 0)
		local moving = dir.Magnitude > 0.05
		local speed = UserInputService:IsKeyDown(Config.Keys.FlyBoost) and Config.FlyBoostSpeed or Config.FlySpeed
		local target = moving and dir.Unit * speed or Vector3.new(0, math.sin(t * 2) * 0.8, 0) -- dururken süzülme
		velocity = velocity:Lerp(target, math.clamp(dt * 6, 0, 1))
		linVel.VectorVelocity = velocity

		-- Yön: kameraya bak, hızlanınca öne eğil
		local flatLook = Vector3.new(camCF.LookVector.X, 0, camCF.LookVector.Z)
		if flatLook.Magnitude < 0.01 then
			flatLook = root.CFrame.LookVector
		end
		local facing = CFrame.lookAt(Vector3.zero, flatLook.Unit)
		local horizontal = Vector3.new(velocity.X, 0, velocity.Z)
		local forwardSpeed = horizontal:Dot(flatLook.Unit)
		local tilt = math.clamp(forwardSpeed / Config.FlyBoostSpeed, -0.4, 1) * math.rad(55)
		alignOri.CFrame = facing * CFrame.Angles(-tilt, 0, 0)
	end)
end

---------------------------------------------------------------------
-- Kamera sarsıntısı
---------------------------------------------------------------------
local shakeUntil, shakePower = 0, 0
RunService:BindToRenderStep("VoidShake", Enum.RenderPriority.Camera.Value + 2, function()
	local now = os.clock()
	if now < shakeUntil then
		local p = shakePower * math.min(1, shakeUntil - now) -- sönümlenen
		camera.CFrame *= CFrame.Angles(
			math.rad((math.random() - 0.5) * p * 2),
			math.rad((math.random() - 0.5) * p * 2),
			math.rad((math.random() - 0.5) * p)
		)
	end
end)

local function shake(power, duration)
	shakePower = power
	shakeUntil = os.clock() + duration
end

---------------------------------------------------------------------
-- Ekran efektleri
---------------------------------------------------------------------
local cc = Instance.new("ColorCorrectionEffect")
cc.Name = "VoidCC"
cc.Parent = Lighting

local function myRoot()
	local char = player.Character
	return char and char:FindFirstChild("HumanoidRootPart")
end

local function distanceTo(pos)
	local root = myRoot()
	return root and (root.Position - pos).Magnitude or math.huge
end

fxRemote.OnClientEvent:Connect(function(kind, a, b, c)
	if kind == "Cooldown" then
		startCooldown(a, b)
	elseif kind == "Shake" then
		local dist = distanceTo(a)
		local falloff = math.clamp(1 - dist / 120, 0, 1)
		if falloff > 0 then
			shake(b * falloff, c)
		end
	elseif kind == "Transform" then
		local root = a and a:FindFirstChild("HumanoidRootPart")
		if root and distanceTo(root.Position) < 80 then
			cc.Contrast, cc.Saturation, cc.Brightness = 0.4, -0.8, -0.15
			tween(cc, 1.2, { Contrast = 0, Saturation = 0, Brightness = 0 })
			shake(0.6, 0.4)
		end
	end
end)

---------------------------------------------------------------------
-- Ultimate cutscene
---------------------------------------------------------------------
local cine = Instance.new("Frame")
cine.Size = UDim2.fromScale(1, 1)
cine.BackgroundTransparency = 1
cine.Visible = false
cine.Parent = gui

local function letterbox(anchorY)
	local f = Instance.new("Frame")
	f.AnchorPoint = Vector2.new(0, anchorY)
	f.Position = UDim2.fromScale(0, anchorY)
	f.Size = UDim2.fromScale(1, 0)
	f.BackgroundColor3 = Color3.new(0, 0, 0)
	f.BorderSizePixel = 0
	f.Parent = cine
	return f
end
local topBar, bottomBar = letterbox(0), letterbox(1)

local subtitle = Instance.new("TextLabel")
subtitle.AnchorPoint = Vector2.new(0.5, 1)
subtitle.Position = UDim2.fromScale(0.5, 0.95)
subtitle.Size = UDim2.fromScale(0.8, 0.06)
subtitle.BackgroundTransparency = 1
subtitle.Font = Enum.Font.Antique
subtitle.TextScaled = true
subtitle.TextColor3 = Color3.fromRGB(230, 235, 250)
subtitle.TextStrokeTransparency = 0.4
subtitle.Text = ""
subtitle.ZIndex = 3
subtitle.Parent = cine

local flash = Instance.new("Frame")
flash.Size = UDim2.fromScale(1, 1)
flash.BackgroundColor3 = Color3.new(0, 0, 0)
flash.BackgroundTransparency = 1
flash.BorderSizePixel = 0
flash.ZIndex = 5
flash.Parent = cine

local function easeInOut(x)
	return -(math.cos(math.pi * math.clamp(x, 0, 1)) - 1) / 2
end

local function runCasterCamera(char, startTime, cfg)
	local root = char:FindFirstChild("HumanoidRootPart")
	if not root then
		return
	end
	local startCF = root.CFrame
	local look = Vector3.new(startCF.LookVector.X, 0, startCF.LookVector.Z).Unit
	local right = look:Cross(Vector3.yAxis)
	local riseEnd = cfg.ArmsOpenAt + 0.8
	local line3 = cfg.Lines[3] and cfg.Lines[3].At or (cfg.ImpactAt - 1.8)

	-- Kameranın takip ettiği nokta: sunucudaki yükselişin aynısı (titremesiz)
	local function basePos(e)
		local h = cfg.RiseHeight * easeInOut(e / riseEnd)
		if e > riseEnd then
			h += math.sin((e - riseEnd) * 1.6) * 0.6
		end
		if e > cfg.EndAt - 0.8 then
			h *= 1 - easeInOut((e - (cfg.EndAt - 0.8)) / 0.8)
		end
		return startCF.Position + Vector3.new(0, h + 1.5, 0)
	end

	local shots = {
		-- 1) Arkadan, aşağıdan silüet (gökyüzüne karşı yükseliş)
		{ from = 0, to = riseEnd, fov = { 60, 55 }, fn = function(a, p)
			local pos = p - look * (10 - a * 3) + right * 2.5 + Vector3.new(0, -5 + a * 2, 0)
			return CFrame.lookAt(pos, p + Vector3.new(0, 2.5, 0))
		end },
		-- 2) Yüze yakın çekim, beyaz gözler, yavaş dönüş
		{ from = riseEnd, to = line3, fov = { 45, 32 }, fn = function(a, p)
			local ang = math.rad(-40 + a * 80)
			local dir = CFrame.fromAxisAngle(Vector3.yAxis, ang):VectorToWorldSpace(look)
			return CFrame.lookAt(p + dir * 6 + Vector3.new(0, 0.4, 0), p + Vector3.new(0, 0.3, 0))
		end },
		-- 3) Önden, aşağıdan kahraman açısı: kollar açık, havada süzülüyor
		{ from = line3, to = cfg.ImpactAt, fov = { 50, 62 }, fn = function(a, p)
			local pos = p + look * (18 + a * 4) + right * (a * 3 - 1.5) - Vector3.new(0, 11, 0)
			return CFrame.lookAt(pos, p + Vector3.new(0, 1, 0))
		end },
		-- 4) Geniş, yukarıdan: herkes gölgeye dönüşüyor
		{ from = cfg.ImpactAt, to = cfg.EndAt, fov = { 72, 80 }, fn = function(a, p)
			local pos = p - look * (28 + a * 14) + Vector3.new(0, 16 + a * 8, 0)
			return CFrame.lookAt(pos, startCF.Position - Vector3.new(0, 4, 0))
		end },
	}

	camera.CameraType = Enum.CameraType.Scriptable
	local impactDone = false
	while true do
		local e = workspace:GetServerTimeNow() - startTime
		if e >= cfg.EndAt or not char.Parent then
			break
		end
		local p = basePos(e)
		for _, s in ipairs(shots) do
			if e >= s.from and e < s.to then
				local a = (e - s.from) / (s.to - s.from)
				camera.CFrame = s.fn(easeInOut(a), p)
				camera.FieldOfView = s.fov[1] + (s.fov[2] - s.fov[1]) * easeInOut(a)
				break
			end
		end
		if not impactDone and e >= cfg.ImpactAt then
			impactDone = true
			flash.BackgroundColor3 = Color3.new(1, 1, 1)
			flash.BackgroundTransparency = 0.1
			tween(flash, 0.6, { BackgroundTransparency = 1 })
		end
		RunService.RenderStepped:Wait()
	end
	camera.CameraType = Enum.CameraType.Custom
	camera.FieldOfView = 70
end

local function showSubtitles(startTime, cfg)
	for i, line in ipairs(cfg.Lines) do
		local nextAt = cfg.Lines[i + 1] and cfg.Lines[i + 1].At or cfg.ImpactAt
		local delayTime = line.At - (workspace:GetServerTimeNow() - startTime)
		task.delay(math.max(0, delayTime), function()
			if not inCutscene then
				return
			end
			subtitle.Text = line.Text
			subtitle.MaxVisibleGraphemes = 0
			subtitle.TextTransparency = 0
			tween(subtitle, 1, { MaxVisibleGraphemes = #line.Text }, Enum.EasingStyle.Linear)
			task.delay(nextAt - line.At - 0.3, function()
				tween(subtitle, 0.25, { TextTransparency = 1 })
			end)
		end)
	end
end

cutsceneRemote.OnClientEvent:Connect(function(char, startTime, cfg)
	local casterRoot = char and char:FindFirstChild("HumanoidRootPart")
	if not casterRoot then
		return
	end
	local isCaster = char == player.Character
	local near = isCaster or distanceTo(casterRoot.Position) < cfg.Radius + 40
	if not near then
		return
	end

	-- Dünya kararır, renkler solar
	tween(cc, 2.5, { Saturation = -0.85, Contrast = 0.35, Brightness = -0.12, TintColor = Color3.fromRGB(190, 195, 215) })
	task.delay(cfg.ImpactAt - (workspace:GetServerTimeNow() - startTime), function()
		cc.Brightness = -0.35
		tween(cc, 0.8, { Brightness = -0.12 })
	end)

	if isCaster then
		inCutscene = true
		stopFlying()
		bar.Visible = false
		cine.Visible = true
		subtitle.Text = ""
		tween(topBar, 0.6, { Size = UDim2.fromScale(1, 0.12) })
		tween(bottomBar, 0.6, { Size = UDim2.fromScale(1, 0.12) })
		showSubtitles(startTime, cfg)
		runCasterCamera(char, startTime, cfg)
		tween(topBar, 0.5, { Size = UDim2.fromScale(1, 0) })
		tween(bottomBar, 0.5, { Size = UDim2.fromScale(1, 0) })
		task.delay(0.5, function()
			cine.Visible = false
			bar.Visible = true
		end)
		inCutscene = false
	else
		task.wait(math.max(0, cfg.EndAt - (workspace:GetServerTimeNow() - startTime)))
	end
	tween(cc, 1.2, { Saturation = 0, Contrast = 0, Brightness = 0, TintColor = Color3.new(1, 1, 1) })
end)

---------------------------------------------------------------------
-- Girdi
---------------------------------------------------------------------
local keyToAbility = {
	[Config.Keys.VoidForm] = "VoidForm",
	[Config.Keys.Grasp] = "Grasp",
	[Config.Keys.Wave] = "Wave",
	[Config.Keys.Ultimate] = "Ultimate",
}

UserInputService.InputBegan:Connect(function(input, processed)
	if processed or inCutscene then
		return
	end
	if input.KeyCode == Config.Keys.Fly then
		if flying then
			stopFlying()
		else
			startFlying()
		end
		return
	end
	local ability = keyToAbility[input.KeyCode]
	if ability then
		abilityRemote:FireServer(ability, camera.CFrame.LookVector)
	end
end)

player.CharacterAdded:Connect(function()
	stopFlying()
	flying = false
	inCutscene = false
	camera.CameraType = Enum.CameraType.Custom
end)

print("[Void] VoidClient hazır - HUD altta görünmeli")
