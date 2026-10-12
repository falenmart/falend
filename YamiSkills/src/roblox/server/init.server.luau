--[[
	YamiSkillsServer (Script) - ServerScriptService içine koy.
	* Herkese "Yami Katana" verir (Config.GiveKatanaToEveryone)
	* Katana + kılıf modelini karaktere kurar, kuşanınca ele alır
	* Yetenek isteklerini doğrular (cooldown, sersemleme, kuşanılmış mı) ve çalıştırır
]]
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("YamiSkills")
local Config = require(Shared:WaitForChild("Config"))
local Util = require(Shared:WaitForChild("Util"))
local KatanaRig = require(Shared:WaitForChild("KatanaRig"))
local Combat = require(script:WaitForChild("Combat"))
local Skills = require(script:WaitForChild("Skills"))
local Boss = require(script:WaitForChild("Boss"))

-- ------------------------------------------------------------------ remotes
local Remotes = Shared:FindFirstChild("Remotes")
if Remotes == nil then
	Remotes = Instance.new("Folder")
	Remotes.Name = "Remotes"
	Remotes.Parent = Shared
end
local function remote(name: string): RemoteEvent
	local r = Remotes:FindFirstChild(name)
	if r == nil then
		r = Instance.new("RemoteEvent")
		r.Name = name
		r.Parent = Remotes
	end
	return r :: RemoteEvent
end
local SkillRequest = remote("SkillRequest")
local SkillEvent = remote("SkillEvent")
local BossEvent = remote("BossEvent")
local MovementRequest = remote("MovementRequest")

local function log(...)
	if Config.Debug then
		print("[YamiSkills]", ...)
	end
end

-- -------------------------------------------------------------------- ağ
local Net = {}
function Net.Cast(ctx, skill: string, data)
	for _, p in ipairs(Players:GetPlayers()) do
		if p ~= ctx.player then
			SkillEvent:FireClient(p, "Cast", skill, ctx.character, data)
		end
	end
end
function Net.Hit(ctx, skill: string, victims: { Model }, data)
	if #victims > 0 then
		SkillEvent:FireAllClients("Hit", skill, ctx.character, victims, data or {})
	end
end
function Net.ToPlayer(player: Player, kind: string, ...)
	SkillEvent:FireClient(player, kind, ...)
end
Skills.Init(Net)

-- ------------------------------------------------------------------- tool
local assets = Shared:WaitForChild("Assets")
local toolTemplate = assets:WaitForChild("YamiKatanaTool") :: Tool

local function giveTool(player: Player)
	local gear = player:FindFirstChild("StarterGear") or player:WaitForChild("StarterGear", 10)
	if gear and not gear:FindFirstChild(Config.ToolName) then
		local t = toolTemplate:Clone()
		t.Name = Config.ToolName
		t.Parent = gear
	end
end

local function hasTool(player: Player, char: Model?): boolean
	local bp = player:FindFirstChildOfClass("Backpack")
	return (bp ~= nil and bp:FindFirstChild(Config.ToolName) ~= nil)
		or (char ~= nil and char:FindFirstChild(Config.ToolName) ~= nil)
end

-- ------------------------------------------------------------------- durum
type State = {
	cooldowns: { [string]: number },
	busyUntil: number,
	combo: number,
	lastM1: number,
	m1Next: number,
	equipToken: number,
}
local states: { [Player]: State } = {}

local function getState(player: Player): State
	local st = states[player]
	if st == nil then
		st = { cooldowns = {}, busyUntil = 0, combo = 0, lastM1 = 0, m1Next = 0, equipToken = 0 }
		states[player] = st
	end
	return st
end

local function onEquip(player: Player, char: Model)
	local st = getState(player)
	st.equipToken += 1
	local token = st.equipToken
	char:SetAttribute("YamiEquipped", true)
	SkillEvent:FireAllClients("Cast", "Equip", char, {}) -- (kendi client'ı kendi karakterini zaten atlar)
	task.delay(Config.EquipGrabTime, function()
		if st.equipToken == token and char.Parent and char:GetAttribute("YamiEquipped") then
			KatanaRig.ToHand(char)
		end
	end)
end

local function onUnequip(player: Player, char: Model)
	local st = getState(player)
	st.equipToken += 1
	char:SetAttribute("YamiEquipped", false)
	KatanaRig.ToHip(char)
end

local function onCharacter(player: Player, char: Model)
	local st = getState(player)
	st.busyUntil = 0
	st.combo = 0
	local hum = char:WaitForChild("Humanoid", 10)
	if hum and hum:IsA("Humanoid") and hum.RigType ~= Enum.HumanoidRigType.R15 then
		warn("[YamiSkills] Bu yetenek seti R15 karakter ister. Game Settings > Avatar > Avatar Type: R15")
	end
	char:SetAttribute("YamiEquipped", false)
	char.ChildAdded:Connect(function(child)
		if child:IsA("Tool") and child.Name == Config.ToolName then
			onEquip(player, char)
		end
	end)
	char.ChildRemoved:Connect(function(child)
		if child:IsA("Tool") and child.Name == Config.ToolName and char.Parent then
			onUnequip(player, char)
		end
	end)
	task.spawn(function()
		if Config.GiveKatanaToEveryone then
			task.wait(1)
			if char.Parent and not hasTool(player, char) then
				local bp = player:FindFirstChildOfClass("Backpack")
				if bp then
					local t = toolTemplate:Clone()
					t.Name = Config.ToolName
					t.Parent = bp
				end
			end
		end
	end)
	-- Avatar yüklenirken gövde parçaları değişirse (paket/Rthro) katanayı yeniden kur
	local rebuildQueued = false
	char.ChildAdded:Connect(function(child)
		if (child.Name == "LowerTorso" or child.Name == "RightHand") and char:FindFirstChild("YamiKatana") then
			if rebuildQueued then
				return
			end
			rebuildQueued = true
			task.delay(0.1, function()
				rebuildQueued = false
				if char.Parent then
					KatanaRig.Setup(char)
					if char:GetAttribute("YamiEquipped") then
						KatanaRig.ToHand(char)
					end
				end
			end)
		end
	end)
	if Config.GiveKatanaToEveryone or hasTool(player, char) then
		KatanaRig.Setup(char)
	else
		-- tool sonradan verilirse katana modelini o zaman kur
		local bp = player:WaitForChild("Backpack", 10)
		if bp then
			local conn
			conn = bp.ChildAdded:Connect(function(child)
				if child.Name == Config.ToolName and char.Parent and char:FindFirstChild("YamiKatana") == nil then
					conn:Disconnect()
					KatanaRig.Setup(char)
				end
			end)
		end
	end
	local existing = char:FindFirstChild(Config.ToolName)
	if existing and existing:IsA("Tool") then
		onEquip(player, char)
	end
end

local function onPlayer(player: Player)
	getState(player)
	if Config.GiveKatanaToEveryone then
		task.spawn(giveTool, player)
	end
	player.CharacterAdded:Connect(function(char)
		onCharacter(player, char)
	end)
	if player.Character then
		task.spawn(onCharacter, player, player.Character)
	end
end

for _, p in ipairs(Players:GetPlayers()) do
	task.spawn(onPlayer, p)
end
Players.PlayerAdded:Connect(onPlayer)
Players.PlayerRemoving:Connect(function(p)
	states[p] = nil
end)

-- ------------------------------------------------------------- istekler
local function reject(player: Player, skill: string, remaining: number?)
	SkillEvent:FireClient(player, "Rejected", skill, remaining or 0)
end

SkillRequest.OnServerEvent:Connect(function(player: Player, skill: any, data: any)
	if typeof(skill) ~= "string" or Config.Skills[skill] == nil then
		return
	end
	if type(data) ~= "table" then
		data = {}
	end
	local st = getState(player)
	local char = player.Character
	local root = Util.getRoot(char)
	local hum = Util.getHumanoid(char)
	if char == nil or root == nil or hum == nil or hum.Health <= 0 then
		return reject(player, skill)
	end
	local tool = char:FindFirstChild(Config.ToolName)
	if tool == nil or not tool:IsA("Tool") then
		return reject(player, skill)
	end
	local now = os.clock()
	if Combat.IsStunned(char) then
		return reject(player, skill)
	end
	if st.busyUntil > now + 0.15 then
		local cd = st.cooldowns[skill]
		return reject(player, skill, if cd then math.max(0, cd - now) else 0)
	end
	local dir = (Util.isFiniteVector(data.Dir) and Util.flat(data.Dir))
		or Util.flat(root.CFrame.LookVector)
		or Vector3.zAxis
	local seed = tonumber(data.Seed)
	seed = if seed and seed == seed then math.floor(math.abs(seed)) % 1073741824 else math.random(1, 1e9)
	local ctx = {
		player = player,
		character = char,
		root = root,
		humanoid = hum,
		dir = dir,
		seed = seed,
		state = st,
		now = now,
	}
	if skill == "M1" then
		local ok = Skills.M1(ctx)
		if not ok then
			reject(player, "M1")
		end
		return
	end
	local cfg = Config.Skills[skill]
	local readyAt = st.cooldowns[skill] or 0
	if readyAt > now + 0.3 then
		return reject(player, skill, readyAt - now)
	end
	st.cooldowns[skill] = now + cfg.Cooldown
	st.busyUntil = now + (cfg.Lock or 0.5)
	local handler = Skills[skill]
	if handler then
		log(player.Name, "->", skill)
		local ok, err = pcall(handler, ctx)
		if not ok then
			warn("[YamiSkills] skill hatası", skill, err)
		end
	end
end)

-- ------------------------------------------------------- hareket (koşu)
if Config.Movement.DisableDefaultShiftLock then
	-- Shift tuşu bizim koşumuz için; Roblox'un Shift Lock'u (sonradan girenler için) kapatılır
	(game:GetService("StarterPlayer") :: any).EnableMouseLockOption = false
end

local lastSprint: { [Player]: number } = {}
MovementRequest.OnServerEvent:Connect(function(player: Player, kind: any, value: any)
	if kind ~= "Sprint" or type(value) ~= "boolean" then
		return
	end
	local now = os.clock()
	if (lastSprint[player] or 0) > now - 0.05 then
		return
	end
	lastSprint[player] = now
	local char = player.Character
	local hum = Util.getHumanoid(char)
	if char == nil or hum == nil or hum.Health <= 0 then
		return
	end
	char:SetAttribute("YamiSprinting", value)
	Combat.SetBaseSpeed(hum, if value then Config.Movement.RunSpeed else Config.Movement.WalkSpeed)
end)
Players.PlayerRemoving:Connect(function(p)
	lastSprint[p] = nil
end)

Boss.Init(BossEvent)

print("[YamiSkills] Yami Sukehiro karanlık büyü seti + Kızıl Kemik İblisi yüklendi (server)")
