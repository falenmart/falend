--[[
	YamiSkillsClient (LocalScript) - StarterPlayer > StarterPlayerScripts içine koy.
	Tuşlar, HUD, animasyonlar, efektler ve kamera burada çalışır.
]]
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")

local Shared = ReplicatedStorage:WaitForChild("YamiSkills")
local Config = require(Shared:WaitForChild("Config"))
local Util = require(Shared:WaitForChild("Util"))
local AnimPlayer = require(Shared:WaitForChild("AnimPlayer"))
local SkillFX = require(Shared:WaitForChild("SkillFX"))
local HUD = require(Shared:WaitForChild("HUD"))
local KatanaRig = require(Shared:WaitForChild("KatanaRig"))

local Remotes = Shared:WaitForChild("Remotes")
local SkillRequest = Remotes:WaitForChild("SkillRequest") :: RemoteEvent
local SkillEvent = Remotes:WaitForChild("SkillEvent") :: RemoteEvent

local player = Players.LocalPlayer

HUD.Init()

-- ------------------------------------------------------------------- durum
local character: Model? = nil
local equippedTool: Tool? = nil
local busyUntil = 0
local cooldowns: { [string]: number } = {}
local pending: { [string]: any } = {}
local m1 = { combo = 0, last = 0, nextAllowed = 0 }

local function log(...)
	if Config.Debug then
		print("[YamiSkills]", ...)
	end
end

local function serverNow(): number
	return workspace:GetServerTimeNow()
end

local function canAct(): boolean
	local char = character
	if char == nil or equippedTool == nil or not Util.isAlive(char) then
		return false
	end
	if os.clock() < busyUntil then
		return false
	end
	local stun = char:GetAttribute("YamiStunUntil")
	if type(stun) == "number" and stun > serverNow() then
		return false
	end
	return true
end

local aimParams = RaycastParams.new()
aimParams.FilterType = Enum.RaycastFilterType.Exclude

local function aimDirection(root: BasePart): Vector3
	local cam = workspace.CurrentCamera
	if cam and UserInputService.MouseEnabled and not UserInputService.TouchEnabled then
		local m = UserInputService:GetMouseLocation()
		local ray = cam:ViewportPointToRay(m.X, m.Y)
		local ignore = { character :: Instance }
		local fx = workspace:FindFirstChild("YamiFX")
		if fx then
			table.insert(ignore, fx)
		end
		aimParams.FilterDescendantsInstances = ignore
		local res = workspace:Raycast(ray.Origin, ray.Direction * 1000, aimParams)
		local target = if res then res.Position else ray.Origin + ray.Direction * 1000
		local d = Util.flat(target - root.Position)
		if d then
			return d
		end
	end
	return Util.flat(cam and cam.CFrame.LookVector) or Util.flat(root.CFrame.LookVector) or Vector3.new(0, 0, -1)
end

local function face(root: BasePart, dir: Vector3)
	root.CFrame = CFrame.lookAt(root.Position, root.Position + dir)
end

-- ------------------------------------------------------------- yetenek kullan
local function tryCast(skill: string)
	if not canAct() then
		return
	end
	local cfg = Config.Skills[skill]
	if cfg == nil or skill == "M1" then
		return
	end
	local now = os.clock()
	if (cooldowns[skill] or 0) > now then
		return
	end
	local char = character :: Model
	local root = Util.getRoot(char)
	if root == nil then
		return
	end
	local dir = aimDirection(root)
	face(root, dir)
	local data = { Dir = dir, Seed = math.random(1, 2 ^ 30) }
	cooldowns[skill] = now + cfg.Cooldown
	busyUntil = now + (cfg.Lock or 0.5)
	HUD.StartCooldown(skill, cfg.Cooldown)
	pending[skill] = SkillFX.Play(skill, char, data, true)
	SkillRequest:FireServer(skill, data)
	log("cast", skill)
end

local function tryM1()
	if not canAct() then
		return
	end
	local cfg = Config.Skills.M1
	local now = os.clock()
	if now < m1.nextAllowed then
		return
	end
	if now - m1.last > cfg.ComboReset then
		m1.combo = 0
	end
	m1.combo = m1.combo % 4 + 1
	m1.last = now
	local i = m1.combo
	m1.nextAllowed = now + (if i == 4 then cfg.Lock[4] + cfg.FinisherCooldown else cfg.Interval)
	busyUntil = now + cfg.Lock[i]
	HUD.SetCombo(i)
	if i == 4 then
		task.delay(cfg.Lock[4] + 0.1, function()
			if m1.combo == 4 then
				HUD.SetCombo(0)
			end
		end)
	end
	local char = character :: Model
	local root = Util.getRoot(char)
	if root == nil then
		return
	end
	local dir = aimDirection(root)
	face(root, dir)
	local data = { Dir = dir, Index = i, Seed = math.random(1, 2 ^ 30) }
	pending.M1 = SkillFX.Play("M1", char, data, true)
	SkillRequest:FireServer("M1", data)
end

task.spawn(function() -- kombo göstergesini zamanla sıfırla
	while true do
		task.wait(0.25)
		if m1.combo > 0 and os.clock() - m1.last > Config.Skills.M1.ComboReset then
			m1.combo = 0
			HUD.SetCombo(0)
		end
	end
end)

HUD.OnActivate = function(skill: string)
	tryCast(skill)
end

local keyToSkill: { [Enum.KeyCode]: string } = {}
for skill, keys in pairs(Config.Keybinds) do
	for _, k in ipairs(keys) do
		keyToSkill[k] = skill
	end
end

UserInputService.InputBegan:Connect(function(input: InputObject, processed: boolean)
	if processed or UserInputService:GetFocusedTextBox() then
		return
	end
	local skill = keyToSkill[input.KeyCode]
	if skill then
		tryCast(skill)
	end
end)

-- -------------------------------------------------------------- tool takibi
local toolConns: { RBXScriptConnection } = {}

local function onEquipped(tool: Tool)
	equippedTool = tool
	for _, c in ipairs(toolConns) do
		c:Disconnect()
	end
	toolConns = {
		tool.Activated:Connect(tryM1),
	}
	HUD.SetVisible(true)
	local char = character
	if char then
		SkillFX.Play("Equip", char, {}, true)
		-- katanayı elde hemen göster (sunucu da aynısını yapar, bu sadece gecikmeyi gizler)
		task.delay(Config.EquipGrabTime, function()
			if equippedTool == tool and character == char then
				KatanaRig.ToHand(char)
			end
		end)
	end
end

local function onUnequipped()
	equippedTool = nil
	for _, c in ipairs(toolConns) do
		c:Disconnect()
	end
	toolConns = {}
	HUD.SetVisible(false)
	if character and character.Parent then
		KatanaRig.ToHip(character)
	end
end

local function setupCharacter(char: Model)
	character = char
	equippedTool = nil
	busyUntil = 0
	m1.combo = 0
	HUD.SetCombo(0)
	HUD.SetVisible(false)
	char.ChildAdded:Connect(function(child)
		if child:IsA("Tool") and child.Name == Config.ToolName then
			onEquipped(child)
		end
	end)
	char.ChildRemoved:Connect(function(child)
		if child == equippedTool then
			onUnequipped()
		end
	end)
	local existing = char:FindFirstChild(Config.ToolName)
	if existing and existing:IsA("Tool") then
		onEquipped(existing)
	end
end

player.CharacterAdded:Connect(setupCharacter)
if player.Character then
	setupCharacter(player.Character)
end

-- ------------------------------------------------- tüm karakterler: Hold + aura
local holdHandles: { [Model]: any } = setmetatable({}, { __mode = "k" }) :: any

local function watchCharacter(plr: Player, char: Model)
	local isLocal = plr == player
	local function updateHold()
		local equipped = char:GetAttribute("YamiEquipped") == true
		local h = holdHandles[char]
		if equipped and h == nil then
			holdHandles[char] = AnimPlayer.Play(char, "Hold", isLocal, { FadeTime = 0.2 }) or false
		elseif not equipped and h ~= nil then
			if h then
				h:Stop(0.2)
			end
			holdHandles[char] = nil
		end
	end
	local function updateBlade()
		local v = char:GetAttribute("YamiBlackBladeUntil")
		SkillFX.SetBlackBlade(char, if type(v) == "number" then v else nil)
	end
	char:GetAttributeChangedSignal("YamiEquipped"):Connect(updateHold)
	char:GetAttributeChangedSignal("YamiBlackBladeUntil"):Connect(updateBlade)
	task.defer(function()
		char:WaitForChild("Humanoid", 10)
		updateHold()
		updateBlade()
	end)
end

local function watchPlayer(plr: Player)
	plr.CharacterAdded:Connect(function(char)
		watchCharacter(plr, char)
	end)
	if plr.Character then
		watchCharacter(plr, plr.Character)
	end
end

for _, plr in ipairs(Players:GetPlayers()) do
	watchPlayer(plr)
end
Players.PlayerAdded:Connect(watchPlayer)

-- ------------------------------------------------------------ sunucu olayları
SkillEvent.OnClientEvent:Connect(function(kind: string, a, b, c, d)
	if kind == "Cast" then
		local skill, char, data = a, b, c
		if typeof(char) == "Instance" and char:IsA("Model") and char ~= character then
			SkillFX.Play(skill, char, data, false)
		end
	elseif kind == "Hit" then
		local skill, attacker, victims, data = a, b, c, d
		if type(victims) == "table" then
			SkillFX.Hit(skill, attacker, victims, data)
		end
	elseif kind == "Rejected" then
		local skill, remaining = a, b
		local cast = pending[skill]
		if cast then
			cast:Cancel()
			pending[skill] = nil
		end
		busyUntil = 0
		if skill ~= "M1" then
			cooldowns[skill] = os.clock() + (tonumber(remaining) or 0)
			if (tonumber(remaining) or 0) > 0 then
				HUD.StartCooldown(skill, remaining)
			else
				HUD.ResetCooldown(skill)
			end
		end
		log("rejected", skill, remaining)
	elseif kind == "Cooldown" then
		local skill, remaining = a, b
		cooldowns[skill] = os.clock() + (tonumber(remaining) or 0)
		HUD.StartCooldown(skill, tonumber(remaining) or 0)
	elseif kind == "BlackBlade" then
		HUD.SetBlackBlade(tonumber(a) or Config.Skills.BlackBlade.Duration)
	end
end)

log("client hazır")
