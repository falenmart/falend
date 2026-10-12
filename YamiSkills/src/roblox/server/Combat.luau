--[[
	Combat (server) - hitbox, hasar, savurma (knockback), sersemletme, yavaşlatma, parça uçurma.
]]
local Debris = game:GetService("Debris")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("YamiSkills")
local Config = require(Shared:WaitForChild("Config"))
local Util = require(Shared:WaitForChild("Util"))

local Combat = {}

export type Victim = { model: Model, humanoid: Humanoid, root: BasePart, player: Player? }

local function findCharacter(part: Instance): Model?
	local cur = part.Parent
	while cur and cur ~= workspace do
		if cur:IsA("Model") and cur:FindFirstChildOfClass("Humanoid") then
			return cur
		end
		cur = cur.Parent
	end
	return nil
end

function Combat.CanHit(attacker: Player?, victimModel: Model): boolean
	local hum = victimModel:FindFirstChildOfClass("Humanoid")
	if hum == nil or hum.Health <= 0 then
		return false
	end
	local victimPlayer = Players:GetPlayerFromCharacter(victimModel)
	if victimPlayer == nil then
		return Config.DamageNPCs
	end
	if attacker and victimPlayer == attacker then
		return false
	end
	if
		Config.TeamCheck
		and attacker
		and not attacker.Neutral
		and not victimPlayer.Neutral
		and attacker.Team ~= nil
		and attacker.Team == victimPlayer.Team
	then
		return false
	end
	return true
end

local function collect(parts: { BasePart }, attacker: Player?, exclude: Instance?): { Victim }
	local seen = {}
	local out = {}
	for _, part in ipairs(parts) do
		local model = findCharacter(part)
		if model and model ~= exclude and not seen[model] then
			seen[model] = true
			local root = Util.getRoot(model) or model.PrimaryPart
			local hum = model:FindFirstChildOfClass("Humanoid")
			if root and hum and Combat.CanHit(attacker, model) then
				table.insert(
					out,
					{ model = model, humanoid = hum, root = root, player = Players:GetPlayerFromCharacter(model) }
				)
			end
		end
	end
	return out
end

local function overlap(exclude: Instance?): OverlapParams
	local params = OverlapParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = if exclude then { exclude } else {}
	return params
end

function Combat.QueryBox(cframe: CFrame, size: Vector3, attackerChar: Model?): { Victim }
	local parts = workspace:GetPartBoundsInBox(cframe, size, overlap(attackerChar))
	if Config.Debug then
		local p = Instance.new("Part")
		p.Anchored, p.CanCollide, p.CanQuery, p.CanTouch = true, false, false, false
		p.Transparency, p.Color, p.Size, p.CFrame = 0.8, Color3.new(1, 0, 0), size, cframe
		p.Parent = workspace
		Debris:AddItem(p, 0.3)
	end
	return collect(parts, attackerChar and Players:GetPlayerFromCharacter(attackerChar), attackerChar)
end

function Combat.QueryRadius(position: Vector3, radius: number, attackerChar: Model?): { Victim }
	local parts = workspace:GetPartBoundsInRadius(position, radius, overlap(attackerChar))
	return collect(parts, attackerChar and Players:GetPlayerFromCharacter(attackerChar), attackerChar)
end

-- ------------------------------------------------------------------ hasar

local function blackBladeMultiplier(attackerChar: Model?): number
	if attackerChar == nil then
		return 1
	end
	local u = attackerChar:GetAttribute("YamiBlackBladeUntil")
	if type(u) == "number" and u > workspace:GetServerTimeNow() then
		return Config.Skills.BlackBlade.DamageMultiplier
	end
	return 1
end

function Combat.Damage(attackerChar: Model?, victim: Victim, amount: number): boolean
	local hum = victim.humanoid
	if hum.Health <= 0 then
		return false
	end
	local attacker = attackerChar and Players:GetPlayerFromCharacter(attackerChar)
	local old = hum:FindFirstChild("creator")
	if old then
		old:Destroy()
	end
	if attacker then
		local tag = Instance.new("ObjectValue")
		tag.Name = "creator"
		tag.Value = attacker
		tag.Parent = hum
		Debris:AddItem(tag, 3)
	end
	hum:TakeDamage(amount * blackBladeMultiplier(attackerChar))
	return true
end

-- ---------------------------------------------------- hareket değiştiriciler

type Mod = { untilT: number, speed: number, noJump: boolean }
type ModState = { list: { Mod }, base: { walk: number, jumpPower: number, jumpHeight: number } }
local mods: { [Humanoid]: ModState } = {}

local function applyMods(hum: Humanoid): boolean
	local st = mods[hum]
	if st == nil then
		return false
	end
	local now = os.clock()
	local speed = math.huge
	local noJump = false
	for i = #st.list, 1, -1 do
		local m = st.list[i]
		if m.untilT <= now then
			table.remove(st.list, i)
		else
			speed = math.min(speed, m.speed)
			noJump = noJump or m.noJump
		end
	end
	if #st.list == 0 or hum.Parent == nil then
		if hum.Parent then
			hum.WalkSpeed = st.base.walk
			hum.JumpPower = st.base.jumpPower
			hum.JumpHeight = st.base.jumpHeight
		end
		mods[hum] = nil
		return false
	end
	hum.WalkSpeed = speed
	if noJump then
		hum.JumpPower = 0
		hum.JumpHeight = 0
	else
		hum.JumpPower = st.base.jumpPower
		hum.JumpHeight = st.base.jumpHeight
	end
	return true
end

-- duration saniye boyunca yürüme hızını speed'e indir (en düşük olan geçerli)
function Combat.Slow(hum: Humanoid, duration: number, speed: number, noJump: boolean?)
	if hum == nil or hum.Parent == nil then
		return
	end
	local st = mods[hum]
	if st == nil then
		st = { list = {}, base = { walk = hum.WalkSpeed, jumpPower = hum.JumpPower, jumpHeight = hum.JumpHeight } }
		mods[hum] = st
		task.spawn(function()
			while applyMods(hum) do
				task.wait(0.05)
			end
		end)
	end
	table.insert(st.list, { untilT = os.clock() + duration, speed = speed, noJump = noJump == true })
	applyMods(hum)
end

-- Koşu gibi kalıcı hız değişimi: aktif yavaşlatma varsa bittiğinde bu hıza dönülür
function Combat.SetBaseSpeed(hum: Humanoid, speed: number)
	local st = mods[hum]
	if st then
		st.base.walk = speed
	else
		hum.WalkSpeed = speed
	end
end

function Combat.Stun(victim: Victim, duration: number)
	if victim.model:GetAttribute("YamiBoss") then
		duration *= 0.3 -- boss'lar kısa sersemler
	end
	Combat.Slow(victim.humanoid, duration, 3, true)
	local untilT = workspace:GetServerTimeNow() + duration
	local cur = victim.model:GetAttribute("YamiStunUntil")
	if type(cur) ~= "number" or cur < untilT then
		victim.model:SetAttribute("YamiStunUntil", untilT)
	end
end

function Combat.IsStunned(model: Model): boolean
	local u = model:GetAttribute("YamiStunUntil")
	return type(u) == "number" and u > workspace:GetServerTimeNow()
end

-- ----------------------------------------------------------- savurma

-- Hedefi velocity hızıyla duration boyunca iter/havalandırır (oyuncu karakterlerinde de çalışır:
-- sunucunun eklediği LinearVelocity, karakterin sahibi olan client'ta simüle edilir).
function Combat.Knockback(root: BasePart, velocity: Vector3, duration: number?)
	local owner = root.Parent
	local resist = owner and owner:GetAttribute("KnockbackResist")
	if type(resist) == "number" then
		velocity *= resist
	end
	for _, old in ipairs(root:GetChildren()) do
		if old.Name == "YamiKnockback" or old.Name == "YamiKnockbackAtt" then
			old:Destroy()
		end
	end
	local att = Instance.new("Attachment")
	att.Name = "YamiKnockbackAtt"
	att.Parent = root
	local lv = Instance.new("LinearVelocity")
	lv.Name = "YamiKnockback"
	lv.Attachment0 = att
	lv.RelativeTo = Enum.ActuatorRelativeTo.World
	lv.VelocityConstraintMode = Enum.VelocityConstraintMode.Vector
	lv.MaxForce = math.huge
	lv.VectorVelocity = velocity
	lv.Parent = root
	local d = duration or 0.2
	Debris:AddItem(lv, d)
	Debris:AddItem(att, d)
	pcall(function()
		if root:GetNetworkOwner() == nil then
			root.AssemblyLinearVelocity = velocity
		end
	end)
end

-- ----------------------------------------------------------- parça uçurma

function Combat.FlingParts(cframe: CFrame, size: Vector3, velocity: Vector3, exclude: Instance?, spread: number?)
	if not Config.FlingUnanchoredParts then
		return
	end
	local parts = workspace:GetPartBoundsInBox(cframe, size, overlap(exclude))
	local done = {}
	local rng = Random.new()
	for _, part in ipairs(parts) do
		local root = part.AssemblyRootPart
		if
			root
			and not done[root]
			and not root.Anchored
			and findCharacter(root) == nil
			and root:FindFirstAncestorOfClass("Tool") == nil
		then
			done[root] = true
			local mass = root.AssemblyMass
			if mass <= Config.MaxFlingMass then
				pcall(function()
					if root:GetNetworkOwner() == nil then
						local s = spread or 0.35
						local v = velocity
							+ Vector3.new(rng:NextNumber(-1, 1), rng:NextNumber(0, 0.5), rng:NextNumber(-1, 1))
								* velocity.Magnitude
								* s
						root:ApplyImpulse(v * mass)
						root:ApplyAngularImpulse(
							Vector3.new(rng:NextNumber(-1, 1), rng:NextNumber(-1, 1), rng:NextNumber(-1, 1)) * mass * 30
						)
					end
				end)
			end
		end
	end
end

-- Sadece oyuncu karakterleri (boss saldırıları için)
function Combat.PlayersInRadius(position: Vector3, radius: number, exclude: Instance?): { Victim }
	local out = {}
	for _, v in ipairs(Combat.QueryRadius(position, radius, exclude :: any)) do
		if v.player then
			table.insert(out, v)
		end
	end
	return out
end

function Combat.PlayersInBox(cframe: CFrame, size: Vector3, exclude: Instance?): { Victim }
	local out = {}
	for _, v in ipairs(Combat.QueryBox(cframe, size, exclude :: any)) do
		if v.player then
			table.insert(out, v)
		end
	end
	return out
end

-- -------------------------------------------------------------- mermi

-- Sunucuda ilerleyen hitbox (görsel her client'ta ayrıca çizilir)
function Combat.Projectile(opts: { [string]: any })
	local origin: Vector3 = opts.Origin
	local dir: Vector3 = opts.Direction
	local speed: number = opts.Speed
	local range: number = opts.Range
	local size: Vector3 = opts.Size
	local exclude: Model? = opts.Exclude
	local onHit: (Victim) -> () = opts.OnHit
	local traveled = 0
	local hitSet = {}
	local conn: RBXScriptConnection
	conn = RunService.Heartbeat:Connect(function(dt)
		local from = traveled
		traveled = math.min(traveled + speed * dt, range)
		local mid = origin + dir * ((from + traveled) / 2)
		local len = (traveled - from) + size.Z
		local cf = CFrame.lookAt(mid, mid + dir)
		for _, v in ipairs(Combat.QueryBox(cf, Vector3.new(size.X, size.Y, len), exclude)) do
			if not hitSet[v.model] then
				hitSet[v.model] = true
				task.spawn(onHit, v)
			end
		end
		if opts.OnStep then
			opts.OnStep(cf, from, traveled)
		end
		if traveled >= range then
			conn:Disconnect()
		end
	end)
end

return Combat
