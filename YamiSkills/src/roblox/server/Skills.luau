--[[
	Skills (server) - her yeteneğin sunucu tarafı: zamanlama, hitbox, hasar, savurma.
	Görseller client'larda (SkillFX). Buradaki zamanlar Config ile animasyonlara eşittir.
]]
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("YamiSkills")
local Config = require(Shared:WaitForChild("Config"))
local Util = require(Shared:WaitForChild("Util"))
local Combat = require(script.Parent:WaitForChild("Combat"))

local Skills = {}

-- Init ile ağ fonksiyonları verilir: Net.Cast(ctx, skill, data), Net.Hit(ctx, skill, victims, data)
local Net: any = nil
function Skills.Init(net)
	Net = net
end

local UP = Vector3.yAxis

local function alive(ctx): boolean
	return Util.isAlive(ctx.character) and ctx.root.Parent ~= nil
end

local function later(ctx, t: number, fn: () -> ())
	task.delay(t, function()
		if alive(ctx) then
			fn()
		end
	end)
end

local function models(victims: { Combat.Victim }): { Model }
	local out = {}
	for _, v in ipairs(victims) do
		table.insert(out, v.model)
	end
	return out
end

-- ------------------------------------------------------------------------- M1
function Skills.M1(ctx): (boolean, number?)
	local cfg = Config.Skills.M1
	local st = ctx.state
	local now = ctx.now
	if now < st.m1Next - 0.1 then
		return false, nil
	end
	if now - st.lastM1 > cfg.ComboReset + 0.2 then
		st.combo = 0
	end
	st.combo = st.combo % 4 + 1
	st.lastM1 = now
	local i = st.combo
	st.m1Next = now + (if i == 4 then cfg.Lock[4] + cfg.FinisherCooldown else cfg.Interval)
	st.busyUntil = now + cfg.Lock[i]
	if i == 4 then
		st.combo = 0
	end
	local dir = ctx.dir
	Combat.Slow(ctx.humanoid, cfg.Lock[i] + 0.1, cfg.WalkSpeed)
	Net.Cast(ctx, "M1", { Dir = dir, Index = i, Seed = ctx.seed })
	later(ctx, cfg.HitTime[i], function()
		local root = ctx.root
		local cf = CFrame.lookAt(root.Position, root.Position + dir) * CFrame.new(0, 0, -cfg.Range / 2 + 0.5)
		local victims = Combat.QueryBox(cf, Vector3.new(cfg.Width, cfg.Height, cfg.Range), ctx.character)
		local hits = {}
		for _, v in ipairs(victims) do
			if Combat.Damage(ctx.character, v, cfg.Damage[i]) then
				Combat.Stun(v, cfg.Stun[i])
				Combat.Knockback(v.root, dir * cfg.Knockback[i] + UP * cfg.Launch[i], if i == 4 then 0.22 else 0.12)
				table.insert(hits, v)
			end
		end
		if #hits > 0 then
			Net.Hit(ctx, "M1", models(hits), { Index = i })
		end
	end)
	return true, nil
end

-- ----------------------------------------------------------------- KARA HİLAL
function Skills.BlackMoon(ctx)
	local cfg = Config.Skills.BlackMoon
	local dir = ctx.dir
	Combat.Slow(ctx.humanoid, cfg.Lock, cfg.WalkSpeed)
	Net.Cast(ctx, "BlackMoon", { Dir = dir, Seed = ctx.seed })
	later(ctx, cfg.ReleaseTime, function()
		local origin = ctx.root.Position + dir * 3 + Vector3.new(0, 0.7, 0)
		Combat.Projectile({
			Origin = origin,
			Direction = dir,
			Speed = cfg.Speed,
			Range = cfg.Range,
			Size = Vector3.new(cfg.Width, cfg.Height, 6),
			Exclude = ctx.character,
			OnHit = function(v)
				if Combat.Damage(ctx.character, v, cfg.Damage) then
					Combat.Stun(v, cfg.Stun)
					Combat.Knockback(v.root, dir * cfg.Knockback + UP * cfg.Launch, 0.2)
					Net.Hit(ctx, "BlackMoon", { v.model }, {})
				end
			end,
			OnStep = function(cf: CFrame, from: number, to: number)
				if math.floor(to / 12) ~= math.floor(from / 12) then
					Combat.FlingParts(cf, Vector3.new(cfg.Width, cfg.Height + 4, 14), dir * 45 + UP * 25, ctx.character)
				end
			end,
		})
	end)
end

-- -------------------------------------------------------------- ÖLÜM SAPLAMASI
function Skills.DeathThrust(ctx)
	local cfg = Config.Skills.DeathThrust
	local dir = ctx.dir
	Combat.Slow(ctx.humanoid, cfg.Lock, cfg.WalkSpeed)
	Net.Cast(ctx, "DeathThrust", { Dir = dir, Seed = ctx.seed })
	later(ctx, cfg.DashTime, function()
		local hitSet = {}
		local t0 = os.clock()
		local conn: RBXScriptConnection
		conn = RunService.Heartbeat:Connect(function()
			if os.clock() - t0 > cfg.DashDuration + 0.15 or not alive(ctx) then
				conn:Disconnect()
				return
			end
			local root = ctx.root
			local cf = CFrame.lookAt(root.Position, root.Position + dir) * CFrame.new(0, 0, -cfg.HitSize.Z / 2 + 1)
			for _, v in ipairs(Combat.QueryBox(cf, cfg.HitSize, ctx.character)) do
				if not hitSet[v.model] then
					hitSet[v.model] = true
					if Combat.Damage(ctx.character, v, cfg.Damage) then
						Combat.Stun(v, cfg.Stun)
						Combat.Knockback(v.root, dir * cfg.Knockback + UP * cfg.Launch, 0.2)
						Net.Hit(ctx, "DeathThrust", { v.model }, {})
					end
				end
			end
		end)
	end)
end

-- ------------------------------------------------------------------ KARA KOZA
function Skills.BlackCocoon(ctx)
	local cfg = Config.Skills.BlackCocoon
	Combat.Slow(ctx.humanoid, cfg.BurstTime + 0.3, 0, true)
	Net.Cast(ctx, "BlackCocoon", { Dir = ctx.dir, Seed = ctx.seed })
	local shield: ForceField? = nil
	later(ctx, cfg.ShellTime, function()
		local ff = Instance.new("ForceField")
		ff.Name = "YamiCocoonShield"
		ff.Visible = false
		ff.Parent = ctx.character
		shield = ff
	end)
	task.delay(cfg.BurstTime, function()
		if shield then
			shield:Destroy()
		end
		if not alive(ctx) then
			return
		end
		local center = ctx.root.Position
		local hits = {}
		for _, v in ipairs(Combat.QueryRadius(center, cfg.Radius, ctx.character)) do
			if Combat.Damage(ctx.character, v, cfg.Damage) then
				local away = Util.flat(v.root.Position - center) or ctx.dir
				Combat.Stun(v, cfg.Stun)
				Combat.Knockback(v.root, away * cfg.Knockback + UP * cfg.Launch, 0.22)
				table.insert(hits, v)
			end
		end
		if #hits > 0 then
			Net.Hit(ctx, "BlackCocoon", models(hits), {})
		end
		Combat.FlingParts(
			CFrame.new(center),
			Vector3.new(cfg.Radius * 2, 14, cfg.Radius * 2),
			UP * 60,
			ctx.character,
			0.9
		)
	end)
end

-- --------------------------------------------------------------- BOYUT KESİĞİ
function Skills.DimensionSlash(ctx)
	local cfg = Config.Skills.DimensionSlash
	local dir = ctx.dir
	Combat.Slow(ctx.humanoid, cfg.Lock, 0, true)
	Net.Cast(ctx, "DimensionSlash", { Dir = dir, Seed = ctx.seed })
	later(ctx, cfg.SlashTime, function()
		local origin = ctx.root.Position
		local basis = CFrame.lookAt(origin, origin + dir)
		local box = basis * CFrame.new(0, cfg.Height * 0.2, -cfg.Length / 2)
		local victims = Combat.QueryBox(box, Vector3.new(cfg.Width, cfg.Height, cfg.Length), ctx.character)
		local hits = {}
		for _, v in ipairs(victims) do
			if Combat.Damage(ctx.character, v, cfg.Damage) then
				Combat.Stun(v, cfg.Stun)
				-- Uzaktakiler biraz gecikmeyle havalanır (kesik dalgası onlara ulaşınca)
				local dist = (v.root.Position - origin).Magnitude
				task.delay(math.clamp(dist / cfg.WaveSpeed, 0, 0.6), function()
					if v.root.Parent then
						Combat.Knockback(v.root, dir * cfg.Knockback + UP * cfg.Launch, 0.28)
					end
				end)
				table.insert(hits, v)
			end
		end
		if #hits > 0 then
			Net.Hit(ctx, "DimensionSlash", models(hits), {})
		end
		-- yol boyunca sabitlenmemiş parçalar havalanır
		local steps = 6
		for k = 1, steps do
			local seg = cfg.Length / steps
			task.delay((k - 0.5) * seg / cfg.WaveSpeed, function()
				local c = basis * CFrame.new(0, cfg.Height * 0.2, -(k - 0.5) * seg)
				Combat.FlingParts(c, Vector3.new(cfg.Width, cfg.Height, seg), dir * 30 + UP * 85, ctx.character, 0.5)
			end)
		end
	end)
end

-- ------------------------------------------------------------------ KARA KILIÇ
function Skills.BlackBlade(ctx)
	local cfg = Config.Skills.BlackBlade
	Net.Cast(ctx, "BlackBlade", { Dir = ctx.dir, Seed = ctx.seed })
	later(ctx, cfg.CoatTime, function()
		local untilT = workspace:GetServerTimeNow() + cfg.Duration
		ctx.character:SetAttribute("YamiBlackBladeUntil", untilT)
		Net.ToPlayer(ctx.player, "BlackBlade", cfg.Duration)
		task.delay(cfg.Duration + 0.1, function()
			if ctx.character.Parent and ctx.character:GetAttribute("YamiBlackBladeUntil") == untilT then
				ctx.character:SetAttribute("YamiBlackBladeUntil", nil)
			end
		end)
	end)
end

return Skills
