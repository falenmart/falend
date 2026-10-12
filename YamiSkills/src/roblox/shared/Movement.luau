--[[
	Movement (client) - TPS kontrolleri.
	Shift (basılı)  : hızlı koşu - sunucu hızı artırır, herkes koşu animasyonunu görür
	Ctrl (aç/kapa)  : nişan kilidi - fare ekran ortasına kilitlenir, kamera omuz üstüne kayar,
	                  karakter her zaman kameranın baktığı yöne döner, ortada nişangâh çıkar
	Mobilde ekranda "KOŞ" ve "NİŞAN" butonları çıkar.
]]
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local Shared = script.Parent
local Config = require(Shared:WaitForChild("Config"))
local Util = require(Shared:WaitForChild("Util"))
local AnimPlayer = require(Shared:WaitForChild("AnimPlayer"))

local Movement = {}

local player = Players.LocalPlayer
local cfg = Config.Movement

local remote: RemoteEvent = nil :: any
local sprintHeld = false
local sprintSent = false
local aiming = false
local aimWasOn = false
local baseFOV = 70
local crosshair: Frame? = nil
local cameraOffset = Vector3.zero
local fovManaged = false

local function isKey(list: { Enum.KeyCode }, key: Enum.KeyCode): boolean
	return table.find(list, key) ~= nil
end

local function humanoid(): Humanoid?
	return Util.getHumanoid(player.Character)
end

function Movement.IsAiming(): boolean
	return aiming
end

function Movement.SetAiming(on: boolean)
	aiming = on
	if crosshair then
		crosshair.Visible = on
	end
end

local function sendSprint(on: boolean)
	if on ~= sprintSent and remote then
		sprintSent = on
		remote:FireServer("Sprint", on)
	end
end

-- -------------------------------------------------------------------- arayüz
local function buildGui()
	local gui = Instance.new("ScreenGui")
	gui.Name = "YamiMovementGui"
	gui.ResetOnSpawn = false
	gui.IgnoreGuiInset = true
	gui.DisplayOrder = 20

	local ch = Instance.new("Frame")
	ch.Name = "Crosshair"
	ch.AnchorPoint = Vector2.new(0.5, 0.5)
	ch.Position = UDim2.fromScale(0.5, 0.5)
	ch.Size = UDim2.fromOffset(28, 28)
	ch.BackgroundTransparency = 1
	ch.Visible = false
	ch.Parent = gui
	local dot = Instance.new("Frame")
	dot.AnchorPoint = Vector2.new(0.5, 0.5)
	dot.Position = UDim2.fromScale(0.5, 0.5)
	dot.Size = UDim2.fromOffset(4, 4)
	dot.BackgroundColor3 = Color3.new(1, 1, 1)
	dot.BorderSizePixel = 0
	dot.Parent = ch
	Instance.new("UICorner", dot).CornerRadius = UDim.new(1, 0)
	for i, offset in ipairs({ Vector2.new(0, -10), Vector2.new(0, 10), Vector2.new(-10, 0), Vector2.new(10, 0) }) do
		local tick = Instance.new("Frame")
		tick.AnchorPoint = Vector2.new(0.5, 0.5)
		tick.Position = UDim2.new(0.5, offset.X, 0.5, offset.Y)
		tick.Size = if i <= 2 then UDim2.fromOffset(2, 7) else UDim2.fromOffset(7, 2)
		tick.BackgroundColor3 = Color3.new(1, 1, 1)
		tick.BorderSizePixel = 0
		tick.Parent = ch
		local stroke = Instance.new("UIStroke")
		stroke.Thickness = 1
		stroke.Color = Color3.new(0, 0, 0)
		stroke.Transparency = 0.4
		stroke.Parent = tick
	end
	crosshair = ch

	if UserInputService.TouchEnabled then
		local function button(text: string, pos: UDim2, onClick: (TextButton) -> ())
			local b = Instance.new("TextButton")
			b.Text = text
			b.Font = Enum.Font.GothamBlack
			b.TextScaled = true
			b.TextColor3 = Color3.new(1, 1, 1)
			b.BackgroundColor3 = Color3.fromRGB(8, 8, 10)
			b.BackgroundTransparency = 0.25
			b.AnchorPoint = Vector2.new(1, 1)
			b.Position = pos
			b.Size = UDim2.fromOffset(70, 70)
			b.Parent = gui
			Instance.new("UICorner", b).CornerRadius = UDim.new(1, 0)
			local s = Instance.new("UIStroke")
			s.Color = Color3.new(1, 1, 1)
			s.Transparency = 0.5
			s.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
			s.Parent = b
			b.Activated:Connect(function()
				onClick(b)
			end)
		end
		button("KOŞ", UDim2.new(1, -110, 1, -175), function(b)
			sprintHeld = not sprintHeld
			b.BackgroundColor3 = if sprintHeld then Color3.fromRGB(150, 20, 24) else Color3.fromRGB(8, 8, 10)
		end)
		button("NİŞAN", UDim2.new(1, -190, 1, -120), function(b)
			Movement.SetAiming(not aiming)
			b.BackgroundColor3 = if aiming then Color3.fromRGB(150, 20, 24) else Color3.fromRGB(8, 8, 10)
		end)
	end
	gui.Parent = player:WaitForChild("PlayerGui")
end

-- --------------------------------------------------------- koşu animasyonu
-- Her client, koşan tüm karakterler için koşu animasyonunu oynatır (yerel = kendi karakterin)
local runHandles: { [Model]: any } = setmetatable({}, { __mode = "k" }) :: any

local function updateRunAnims()
	for _, plr in ipairs(Players:GetPlayers()) do
		local char = plr.Character
		local hum = Util.getHumanoid(char)
		local root = Util.getRoot(char)
		if char and hum and root then
			local vel = root.AssemblyLinearVelocity
			local speed = Vector3.new(vel.X, 0, vel.Z).Magnitude
			local state = hum:GetState()
			local grounded = state == Enum.HumanoidStateType.Running or state == Enum.HumanoidStateType.RunningNoPhysics
			local want = char:GetAttribute("YamiSprinting") == true and speed > 8 and grounded and hum.Health > 0
			local h = runHandles[char]
			if want and h == nil then
				runHandles[char] = AnimPlayer.Play(char, "Run", plr == player, { FadeTime = 0.15 }) or false
			elseif not want and h ~= nil then
				if h then
					h:Stop(0.18)
				end
				runHandles[char] = nil
			elseif want and h then
				h:AdjustSpeed(math.clamp(speed / cfg.RunSpeed, 0.6, 1.4))
			end
		end
	end
end

-- -------------------------------------------------------------- her kare
local function onRender(dt: number)
	local hum = humanoid()
	local cam = workspace.CurrentCamera
	if hum == nil or cam == nil then
		return
	end
	local root = Util.getRoot(player.Character)
	local alive = hum.Health > 0
	local moving = hum.MoveDirection.Magnitude > 0.1
	sendSprint(sprintHeld and moving and alive)

	-- nişan kilidi
	local target = if aiming and alive then cfg.AimCameraOffset else Vector3.zero
	cameraOffset = cameraOffset:Lerp(target, math.clamp(dt * 12, 0, 1))
	hum.CameraOffset = cameraOffset
	if aiming and alive then
		UserInputService.MouseBehavior = Enum.MouseBehavior.LockCenter
		hum.AutoRotate = false
		if root and not hum.Sit and hum.PlatformStand == false then
			local look = Util.flat(cam.CFrame.LookVector)
			if look then
				root.CFrame = CFrame.lookAt(root.Position, root.Position + look)
			end
		end
		aimWasOn = true
	elseif aimWasOn then
		aimWasOn = false
		UserInputService.MouseBehavior = Enum.MouseBehavior.Default
		hum.AutoRotate = true
	end

	-- görüş açısı (sadece koşu/nişan sırasında ve sonrasında dönüşte yönetilir;
	-- yeteneklerin FOV vuruşlarıyla çakışmasın)
	local fov: number? = nil
	if aiming then
		fov = cfg.AimFOV
	elseif sprintSent then
		fov = cfg.RunFOV
	elseif fovManaged then
		fov = baseFOV
		if math.abs(cam.FieldOfView - baseFOV) < 0.3 then
			cam.FieldOfView = baseFOV
			fovManaged = false
			fov = nil
		end
	end
	if fov then
		fovManaged = true
		cam.FieldOfView += (fov - cam.FieldOfView) * math.clamp(dt * 8, 0, 1)
	end
end

function Movement.Init(movementRemote: RemoteEvent)
	remote = movementRemote
	local cam = workspace.CurrentCamera
	baseFOV = if cam then cam.FieldOfView else 70
	buildGui()

	UserInputService.InputBegan:Connect(function(input, processed)
		if UserInputService:GetFocusedTextBox() then
			return
		end
		if isKey(cfg.SprintKeys, input.KeyCode) then
			sprintHeld = true
		elseif isKey(cfg.AimKeys, input.KeyCode) and not processed then
			if cfg.AimToggle then
				Movement.SetAiming(not aiming)
			else
				Movement.SetAiming(true)
			end
		end
	end)
	UserInputService.InputEnded:Connect(function(input)
		if isKey(cfg.SprintKeys, input.KeyCode) then
			sprintHeld = false
		elseif isKey(cfg.AimKeys, input.KeyCode) and not cfg.AimToggle then
			Movement.SetAiming(false)
		end
	end)
	player.CharacterAdded:Connect(function()
		sprintSent = false
		cameraOffset = Vector3.zero
	end)

	-- kamera script'inden SONRA çalışmalı (fare kilidini ve kamera kaymasını ezmesin)
	RunService:BindToRenderStep("YamiMovement", Enum.RenderPriority.Camera.Value + 2, onRender)
	RunService.Heartbeat:Connect(updateRunAnims)
end

return Movement
