--[[
	Boss (server) - Kızıl Kemik İblisi yapay zekâsı.
	En yakın oyuncuya yürür, menzile göre saldırı seçer:
	  Slash : sağ bıçakla geniş yatay kesik (yakın)
	  Slam  : iki bıçağı kaldırıp önüne vurur, şok dalgası (yakın-orta)
	  Lunge : eğilip ileri atılır (orta mesafe)
	  Roar  : kükrer, taçtan kırmızı enerji; oyuncuların altından dikenler fışkırır (uzak)
	Hasarlar Config.Boss.Attacks içinde ve bilerek çok düşük.
	Görsel efekt ve animasyonlar client'ta (BossFX); sunucu "BossEvent" ile haber verir.
]]
local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("YamiSkills")
local Config = require(Shared:WaitForChild("Config"))
local Util = require(Shared:WaitForChild("Util"))
local BossRig = require(Shared:WaitForChild("BossRig"))
local Combat = require(script.Parent:WaitForChild("Combat"))

local Boss = {}

local BossEvent: RemoteEvent = nil :: any
local UP = Vector3.yAxis

local function groundBelow(pos: Vector3, exclude: { Instance }): Vector3
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = exclude
	local res = workspace:Raycast(pos + Vector3.new(0, 60, 0), Vector3.new(0, -400, 0), params)
	return if res then res.Position else pos
end

local function spawnCFrame(): CFrame
	local marker = workspace:FindFirstChild("YamiBossSpawn", true)
	local exclude = Util.characterList()
	if marker and marker:IsA("BasePart") then
		table.insert(exclude, marker)
		local g = groundBelow(marker.Position, exclude)
		local look = marker.CFrame.LookVector
		return CFrame.lookAt(g, g + Vector3.new(look.X, 0, look.Z))
	end
	local g = groundBelow(Config.Boss.SpawnPosition, exclude)
	return CFrame.lookAt(g, g + Vector3.new(0, 0, 1)) -- varsayılan: oyunculara (+Z) bakar
end

local function nearestPlayer(root: BasePart): (Model?, BasePart?, number)
	local best, bestRoot, bestD = nil, nil, Config.Boss.AggroRange
	for _, p in ipairs(Players:GetPlayers()) do
		local char = p.Character
		local r = Util.getRoot(char)
		if char and r and Util.isAlive(char) then
			local d = (r.Position - root.Position).Magnitude
			if d < bestD then
				best, bestRoot, bestD = char, r, d
			end
		end
	end
	return best, bestRoot, bestD
end

local function models(victims): { Model }
	local out = {}
	for _, v in ipairs(victims) do
		table.insert(out, v.model)
	end
	return out
end

local function hitPlayers(model: Model, attack: string, victims, damage: number, push: (any) -> Vector3)
	local hits = {}
	for _, v in ipairs(victims) do
		if Combat.Damage(model, v, damage) then
			Combat.Knockback(v.root, push(v), 0.2)
			table.insert(hits, v)
		end
	end
	if #hits > 0 then
		BossEvent:FireAllClients("Hit", model, attack, models(hits))
	end
end

local function runBoss(model: Model)
	local cfg = Config.Boss
	local A = cfg.Attacks
	local root = model.PrimaryPart :: BasePart
	local hum = model:FindFirstChildOfClass("Humanoid") :: Humanoid
	local busy = false
	local ready: { [string]: number } = { Slash = 0, Slam = 2, Lunge = 4, Roar = 6 }
	local alive = true

	local function face(pos: Vector3)
		local flat = Vector3.new(pos.X, root.Position.Y, pos.Z)
		if (flat - root.Position).Magnitude > 0.5 then
			root.CFrame = CFrame.lookAt(root.Position, flat)
		end
	end

	local function attack(name: string, targetRoot: BasePart)
		local a = A[name]
		local now = os.clock()
		busy = true
		ready[name] = now + a.Cooldown
		hum:MoveTo(root.Position)
		face(targetRoot.Position)
		local dir = Util.flat(targetRoot.Position - root.Position) or Util.flat(root.CFrame.LookVector) or Vector3.zAxis
		local data: { [string]: any } = { Dir = dir, Seed = math.random(1, 1e6) }
		local exclude = { model :: Instance }

		if name == "Slash" then
			BossEvent:FireAllClients("Attack", model, name, data)
			task.delay(a.HitTime, function()
				if not alive then
					return
				end
				local cf = CFrame.lookAt(root.Position, root.Position + dir) * CFrame.new(0, 0, -a.Range / 2)
				local victims = Combat.PlayersInBox(cf, Vector3.new(a.Range * 1.6, 14, a.Range), model)
				hitPlayers(model, name, victims, a.Damage, function()
					return dir * a.Knockback + UP * 15
				end)
			end)
		elseif name == "Slam" then
			local impact = groundBelow(root.Position + dir * 15, exclude) -- bıçak uçlarının yere değdiği yer
			data.Impact = impact
			data.Radius = a.Radius
			BossEvent:FireAllClients("Attack", model, name, data)
			task.delay(a.HitTime, function()
				if not alive then
					return
				end
				local victims = Combat.PlayersInRadius(impact, a.Radius, model)
				hitPlayers(model, name, victims, a.Damage, function(v)
					return (Util.flat(v.root.Position - impact) or dir) * a.Knockback + UP * 30
				end)
			end)
		elseif name == "Lunge" then
			BossEvent:FireAllClients("Attack", model, name, data)
			task.delay(a.LungeTime, function()
				if not alive then
					return
				end
				Combat.Knockback(root, dir * a.Speed / math.max(cfg.KnockbackResist, 0.01), 0.3)
				local hitSet = {}
				local t0 = os.clock()
				local conn: RBXScriptConnection
				conn = RunService.Heartbeat:Connect(function()
					if os.clock() - t0 > 0.45 or not alive then
						conn:Disconnect()
						return
					end
					local cf = CFrame.lookAt(root.Position, root.Position + dir) * CFrame.new(0, 0, -6)
					local fresh = {}
					for _, v in ipairs(Combat.PlayersInBox(cf, Vector3.new(16, 14, 14), model)) do
						if not hitSet[v.model] then
							hitSet[v.model] = true
							table.insert(fresh, v)
						end
					end
					if #fresh > 0 then
						hitPlayers(model, name, fresh, a.Damage, function()
							return dir * a.Knockback + UP * 20
						end)
					end
				end)
			end)
		elseif name == "Roar" then
			local targets = {}
			for _, p in ipairs(Players:GetPlayers()) do
				local r = Util.getRoot(p.Character)
				if r and Util.isAlive(p.Character) and (r.Position - root.Position).Magnitude <= a.Range then
					table.insert(targets, groundBelow(r.Position, Util.characterList()))
				end
			end
			data.Targets = targets
			data.SpikeRadius = a.SpikeRadius
			BossEvent:FireAllClients("Attack", model, name, data)
			task.delay(a.BurstTime, function()
				if not alive then
					return
				end
				-- kükreme dalgası: yakındakileri iter (hasarsız)
				for _, v in ipairs(Combat.PlayersInRadius(root.Position, 22, model)) do
					local away = Util.flat(v.root.Position - root.Position) or dir
					Combat.Knockback(v.root, away * a.Knockback + UP * 12, 0.18)
				end
			end)
			task.delay(a.BurstTime + a.SpikeDelay, function()
				if not alive then
					return
				end
				local victims, seen = {}, {}
				for _, pos in ipairs(targets) do
					for _, v in ipairs(Combat.PlayersInRadius(pos, a.SpikeRadius, model)) do
						if not seen[v.model] then
							seen[v.model] = true
							table.insert(victims, v)
						end
					end
				end
				hitPlayers(model, name, victims, a.Damage, function()
					return UP * 55
				end)
			end)
		end
		task.delay(a.Duration, function()
			busy = false
		end)
	end

	hum.Died:Connect(function()
		alive = false
		root.Anchored = true
		BossEvent:FireAllClients("Death", model)
		task.delay(4, function()
			model:Destroy()
		end)
		task.delay(cfg.RespawnTime, Boss.Spawn)
	end)

	task.spawn(function()
		while alive and model.Parent do
			task.wait(0.12)
			if busy or not alive then
				continue
			end
			if Combat.IsStunned(model) then
				hum:MoveTo(root.Position)
				continue
			end
			local target, tRoot, d = nearestPlayer(root)
			if target == nil or tRoot == nil then
				hum:MoveTo(root.Position)
				continue
			end
			local now = os.clock()
			local choice: string? = nil
			if d <= A.Slash.Range and now >= ready.Slash then
				choice = "Slash"
			elseif d <= A.Slam.Range and now >= ready.Slam then
				choice = "Slam"
			elseif d >= A.Lunge.MinRange and d <= A.Lunge.Range and now >= ready.Lunge then
				choice = "Lunge"
			elseif d <= A.Roar.Range and now >= ready.Roar and math.random() < 0.5 then
				choice = "Roar"
			end
			if choice then
				attack(choice, tRoot)
			elseif d > 10 then
				hum:MoveTo(tRoot.Position)
			else
				hum:MoveTo(root.Position)
				face(tRoot.Position)
			end
		end
	end)
end

function Boss.Spawn()
	local cf = spawnCFrame()
	local model = BossRig.Build(cf)
	model.Parent = workspace
	CollectionService:AddTag(model, "YamiBoss")
	local root = model.PrimaryPart :: BasePart
	pcall(function()
		root:SetNetworkOwner(nil)
	end)
	runBoss(model)
	return model
end

function Boss.Init(bossEvent: RemoteEvent)
	BossEvent = bossEvent
	if Config.Boss.Enabled then
		task.defer(Boss.Spawn)
	end
end

return Boss
