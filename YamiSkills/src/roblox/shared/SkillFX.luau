--[[
	SkillFX (client) - her yeteneğin görsel/işitsel koreografisi.
	Kendi karakterin için girişte hemen (tahmin / prediction) oynar, başkaları için sunucudan
	"Cast" gelince oynar. Hasar ve havalandırma sunucudadır; burada sadece görüntü.

	SkillFX.Play(skill, character, data, isLocal) -> cast  (cast:Cancel())
	SkillFX.Hit(skill, attacker, victims, data)
	SkillFX.SetBlackBlade(character, untilServerTime)
]]
local Debris = game:GetService("Debris")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local Shared = script.Parent
local Config = require(Shared:WaitForChild("Config"))
local Util = require(Shared:WaitForChild("Util"))
local AnimPlayer = require(Shared:WaitForChild("AnimPlayer"))
local VFX = require(Shared:WaitForChild("VFX"))
local RockFX = require(Shared:WaitForChild("RockFX"))
local CameraShake = require(Shared:WaitForChild("CameraShake"))
local ScreenFX = require(Shared:WaitForChild("ScreenFX"))
local SFX = require(Shared:WaitForChild("SFX"))

local SkillFX = {}

local ns = VFX.ns

-- ------------------------------------------------------------------- cast nesnesi

local Cast = {}
Cast.__index = Cast

function Cast.new(character: Model)
	return setmetatable({ character = character, cancelled = false, cleanups = {}, anim = nil }, Cast)
end

function Cast:Delay(t: number, fn: () -> ())
	task.delay(t, function()
		if not self.cancelled and Util.isAlive(self.character) then
			fn()
		end
	end)
end

function Cast:OnCancel(fn: () -> ())
	table.insert(self.cleanups, fn)
end

function Cast:Cancel()
	if self.cancelled then
		return
	end
	self.cancelled = true
	for _, fn in ipairs(self.cleanups) do
		pcall(fn)
	end
	if self.anim then
		self.anim:Stop(0.12)
	end
end

-- ---------------------------------------------------------------- yardımcılar

local function katana(char: Model): Model?
	local m = char:FindFirstChild("YamiKatana")
	return if m and m:IsA("Model") then m else nil
end

local function blade(char: Model): BasePart?
	local m = katana(char)
	local b = m and m:FindFirstChild("Blade")
	return if b and b:IsA("BasePart") then b else nil
end

local function tipAttachment(char: Model): Attachment?
	local b = blade(char)
	local a = b and b:FindFirstChild("TrailTip")
	return if a and a:IsA("Attachment") then a else nil
end

local function trail(char: Model): Trail?
	local b = blade(char)
	local t = b and b:FindFirstChild("YamiTrail")
	return if t and t:IsA("Trail") then t else nil
end

local blackBladeUntil: { [Model]: number } = setmetatable({}, { __mode = "k" }) :: any

local function bladeCoated(char: Model): boolean
	local u = blackBladeUntil[char]
	return u ~= nil and u > workspace:GetServerTimeNow()
end

local function enableTrail(cast, char: Model, delayT: number, duration: number)
	cast:Delay(delayT, function()
		local t = trail(char)
		if t then
			t.Enabled = true
			task.delay(duration, function()
				if not bladeCoated(char) and t.Parent then
					t.Enabled = false
				end
			end)
		end
	end)
end

local rotationLocks: { [Model]: any } = setmetatable({}, { __mode = "k" }) :: any
local function lockRotation(char: Model, duration: number)
	local hum = Util.getHumanoid(char)
	if hum == nil then
		return
	end
	local token = {}
	rotationLocks[char] = token
	hum.AutoRotate = false
	task.delay(duration, function()
		if rotationLocks[char] == token and hum.Parent then
			hum.AutoRotate = true
			rotationLocks[char] = nil
		end
	end)
end

local function pushVelocity(root: BasePart, velocity: Vector3, duration: number, cast)
	local att = Instance.new("Attachment")
	att.Name = "YamiMoveAtt"
	att.Parent = root
	local lv = Instance.new("LinearVelocity")
	lv.Name = "YamiMove"
	lv.Attachment0 = att
	lv.RelativeTo = Enum.ActuatorRelativeTo.World
	lv.VelocityConstraintMode = Enum.VelocityConstraintMode.Vector
	lv.MaxForce = math.huge
	lv.VectorVelocity = velocity
	lv.Parent = root
	local function stop()
		if lv.Parent then
			lv:Destroy()
		end
		if att.Parent then
			att:Destroy()
		end
	end
	task.delay(duration, stop)
	if cast then
		cast:OnCancel(stop)
	end
end

local function nearby(position: Vector3, isLocal: boolean): boolean
	return isLocal or ScreenFX.InRange(position)
end

local function chestCF(root: BasePart, dir: Vector3, up: number?): CFrame
	local p = root.Position + Vector3.new(0, up or 0.9, 0)
	return CFrame.lookAt(p, p + dir)
end

local function localCharacter(): Model?
	return Players.LocalPlayer.Character
end

-- ------------------------------------------------------------------------- M1

local M1_ROLL = { 215, 6, 40, -90 }
local M1_SLASH_T = { 0.1, 0.1, 0.1, 0.17 }

local function M1(cast, char: Model, data, isLocal: boolean)
	local cfg = Config.Skills.M1
	local i = math.clamp(tonumber(data.Index) or 1, 1, 4)
	local root = Util.getRoot(char)
	if root == nil then
		return
	end
	local dir = Util.flat(data.Dir) or Util.flat(root.CFrame.LookVector) or Vector3.zAxis
	cast.anim = AnimPlayer.Play(char, cfg.Animations[i], isLocal, { FadeTime = 0.05 })
	if isLocal then
		lockRotation(char, cfg.Lock[i])
		pushVelocity(root, dir * (if i == 4 then 30 else 16), if i == 4 then 0.15 else 0.09, cast)
	end
	enableTrail(cast, char, 0.06, 0.3)
	cast:Delay(0.08, function()
		SFX.Play(if i == 4 then "HeavySwing" else "Swing", root)
	end)
	cast:Delay(M1_SLASH_T[i], function()
		VFX.Crescent(chestCF(root, dir, if i == 4 then 1.2 else 0.9), {
			Radius = if i == 4 then 6.5 else 5.4,
			Roll = M1_ROLL[i],
			Sweep = 60,
			Duration = if i == 4 then 0.32 else 0.26,
			Width = if i == 4 then 1.25 else 1,
		})
	end)
	if i == 4 then
		cast:Delay(0.25, function()
			local ground = Util.ground(root.Position + dir * 4.5)
			if ground then
				local pos = ground.Position
				RockFX.Crater(pos, {
					Ground = ground,
					Radius = 4.5,
					Count = 9,
					SizeMin = 0.9,
					SizeMax = 1.8,
					Duration = 1.6,
					Seed = data.Seed,
				})
				RockFX.Debris(pos, { Ground = ground, Count = 6, UpMin = 25, UpMax = 45, Seed = data.Seed })
				VFX.Shockwave(CFrame.new(pos + Vector3.new(0, 0.2, 0)), { Radius = 12, Duration = 0.4 })
				VFX.GroundCracks(pos + Vector3.new(0, 0.05, 0), 6, 4, 1.5, data.Seed)
				SFX.Play("Boom", pos, { Volume = 0.55, Speed = 1.5 })
				if nearby(pos, isLocal) then
					CameraShake.ShakeAt(pos, 1.1, 0.35, 90)
				end
			end
		end)
	end
end

-- ----------------------------------------------------------------- KARA HİLAL

local function moonProjectile(origin: Vector3, dir: Vector3, seed: number)
	local cfg = Config.Skills.BlackMoon
	local radius = 7.5
	local proj = VFX.CrescentProjectile(radius)
	local att = VFX.Attachment(origin)
	local smoke = VFX.Emitter(att, "Smoke", {
		Rate = 90,
		Lifetime = NumberRange.new(0.35, 0.6),
		Speed = NumberRange.new(1, 4),
		Size = ns({ { 0, 3 }, { 1, 6 } }),
	})
	local embers = VFX.Emitter(att, "Embers", { Rate = 50, Speed = NumberRange.new(6, 14) })
	local rng = Random.new(seed)
	local t0 = os.clock()
	local lastMark = 0
	local conn: RBXScriptConnection
	conn = RunService.RenderStepped:Connect(function()
		local dist = (os.clock() - t0) * cfg.Speed
		if dist >= cfg.Range then
			conn:Disconnect()
			proj:Destroy()
			smoke.Enabled = false
			embers.Enabled = false
			Debris:AddItem(att, 1)
			return
		end
		local pos = origin + dir * dist
		local fade = if dist > cfg.Range - 30 then (dist - (cfg.Range - 30)) / 30 else 0
		local wobble = math.sin(dist * 0.15) * 2
		proj:Set(
			CFrame.lookAt(pos, pos + dir) * CFrame.Angles(0, 0, math.rad(wobble)) * CFrame.new(0, 0, radius * 0.7),
			fade
		)
		att.WorldPosition = pos
		if dist - lastMark > 9 then
			lastMark = dist
			local g = Util.ground(pos)
			if g and pos.Y - g.Position.Y < 7 then
				VFX.GroundScar(g.Position - dir * 9, g.Position, 0.7, 1.4, g.Position.Y)
				RockFX.Debris(g.Position, {
					Ground = g,
					Count = 2,
					UpMin = 14,
					UpMax = 32,
					OutMin = 4,
					OutMax = 12,
					SizeMin = 0.4,
					SizeMax = 1.1,
					DustCount = 2,
					Seed = rng:NextInteger(1, 1e6),
				})
			end
		end
	end)
end

local function BlackMoon(cast, char: Model, data, isLocal: boolean)
	local cfg = Config.Skills.BlackMoon
	local root = Util.getRoot(char)
	if root == nil then
		return
	end
	local dir = Util.flat(data.Dir) or Util.flat(root.CFrame.LookVector) or Vector3.zAxis
	cast.anim = AnimPlayer.Play(char, cfg.Animation, isLocal)
	if isLocal then
		lockRotation(char, cfg.Lock)
	end
	local b = blade(char)
	if b then
		local e = VFX.Aura(b, "Wisps", { Rate = 80 })
		local function off()
			e.Enabled = false
			Debris:AddItem(e, 1)
		end
		task.delay(cfg.ReleaseTime + 0.05, off)
		cast:OnCancel(off)
	end
	enableTrail(cast, char, 0.26, 0.4)
	cast:Delay(0.27, function()
		SFX.Play("HeavySwing", root)
	end)
	cast:Delay(cfg.ReleaseTime, function()
		local origin = root.Position + dir * 3 + Vector3.new(0, 0.7, 0)
		VFX.Crescent(chestCF(root, dir, 0.7), { Radius = 6.8, Roll = 180, Sweep = 75, Duration = 0.3, Grow = 1.25 })
		VFX.Shockwave(
			CFrame.lookAt(origin, origin + dir) * CFrame.Angles(-math.pi / 2, 0, 0),
			{ Radius = 8, Duration = 0.3 }
		)
		moonProjectile(origin, dir, tonumber(data.Seed) or 1)
		SFX.Play("Boom", origin, { Volume = 0.45, Speed = 1.6 })
		if nearby(origin, isLocal) then
			CameraShake.ShakeAt(origin, if isLocal then 1.3 else 0.9, 0.4, 120)
		end
		if isLocal then
			ScreenFX.FOVKick(9, 0.08, 0.35)
		end
	end)
end

-- -------------------------------------------------------------- ÖLÜM SAPLAMASI

local function DeathThrust(cast, char: Model, data, isLocal: boolean)
	local cfg = Config.Skills.DeathThrust
	local root = Util.getRoot(char)
	if root == nil then
		return
	end
	local dir = Util.flat(data.Dir) or Util.flat(root.CFrame.LookVector) or Vector3.zAxis
	cast.anim = AnimPlayer.Play(char, cfg.Animation, isLocal)
	if isLocal then
		lockRotation(char, cfg.Lock)
	end
	-- uçta karanlık toplanır
	local tip = tipAttachment(char)
	if tip then
		local e = VFX.Emitter(tip, "Smoke", {
			Rate = 70,
			Size = ns({ { 0, 1.2 }, { 1, 0.1 } }),
			Speed = NumberRange.new(0.5, 2),
			Lifetime = NumberRange.new(0.25, 0.4),
		})
		local function off()
			e.Enabled = false
			Debris:AddItem(e, 0.6)
		end
		task.delay(cfg.DashTime + cfg.DashDuration, off)
		cast:OnCancel(off)
	end
	enableTrail(cast, char, cfg.DashTime - 0.03, cfg.DashDuration + 0.2)
	cast:Delay(cfg.DashTime, function()
		local startPos = root.Position
		SFX.Play("Dash", root)
		VFX.Shockwave(
			CFrame.lookAt(startPos, startPos + dir) * CFrame.Angles(-math.pi / 2, 0, 0),
			{ Radius = 7, Duration = 0.32 }
		)
		VFX.Burst(startPos - Vector3.new(0, 2.5, 0), "Dust", 6, {
			Color = ColorSequence.new(Color3.fromRGB(70, 66, 62)),
		})
		if isLocal then
			pushVelocity(root, dir * cfg.DashSpeed, cfg.DashDuration, cast)
			ScreenFX.FOVKick(14, 0.1, 0.45)
			CameraShake.Shake(0.7, 0.3)
		end
		for k = 0, 4 do
			cast:Delay(k * cfg.DashDuration / 5, function()
				VFX.Afterimage(char, { Lifetime = 0.32, Transparency = 0.25 + k * 0.08 })
			end)
		end
		cast:Delay(cfg.DashDuration, function()
			local endPos = root.Position
			local len = (endPos - startPos).Magnitude
			if len > 1 then
				local streak = VFX.Part({
					Size = Vector3.new(0.7, 0.7, len),
					CFrame = CFrame.lookAt(
						(startPos + endPos) / 2 + Vector3.new(0, 0.6, 0),
						endPos + Vector3.new(0, 0.6, 0)
					),
				})
				VFX.Outline(streak, 0.3)
				VFX.Animate(0.45, function(a)
					local w = 0.7 * (1 - a) + 0.05
					streak.Size = Vector3.new(w, w, len)
					streak.Transparency = a
					if a >= 1 then
						streak:Destroy()
					end
				end)
			end
			VFX.Burst(endPos, "Smoke", 10)
			RockFX.Debris(endPos, { Count = 4, UpMin = 14, UpMax = 28, Seed = data.Seed })
		end)
	end)
end

-- ------------------------------------------------------------------ KARA KOZA

local function BlackCocoon(cast, char: Model, data, isLocal: boolean)
	local cfg = Config.Skills.BlackCocoon
	local root = Util.getRoot(char)
	if root == nil then
		return
	end
	cast.anim = AnimPlayer.Play(char, cfg.Animation, isLocal)
	if isLocal then
		lockRotation(char, cfg.Lock)
	end
	-- dışarıdan içeri toplanan karanlık
	local conv = VFX.Part({ Size = Vector3.new(24, 24, 24), Transparency = 1, CFrame = root.CFrame })
	local ce = VFX.Emitter(conv, "Implode", { Rate = 110 })
	task.delay(cfg.ShellTime + 0.15, function()
		ce.Enabled = false
	end)
	Debris:AddItem(conv, cfg.ShellTime + 1)
	SFX.Play("Shell", root)
	local shell: BasePart? = nil
	local follow: RBXScriptConnection? = nil
	local function cleanupShell()
		if follow then
			follow:Disconnect()
		end
		if shell then
			shell:Destroy()
		end
	end
	cast:OnCancel(cleanupShell)
	cast:Delay(cfg.ShellTime, function()
		local size = cfg.ShellSize
		local mesh = VFX.Mesh("Cocoon", size / 2.3)
		local s: BasePart
		if mesh then
			s = mesh
			mesh.Color = Config.Theme.Core
			mesh.Material = Enum.Material.Neon
		else
			s = VFX.Part({ Shape = Enum.PartType.Ball, Size = Vector3.one * size })
		end
		shell = s
		VFX.Outline(s, 0.15)
		local wisps = VFX.Emitter(s, "Wisps", {
			Rate = 45,
			Shape = Enum.ParticleEmitterShape.Sphere,
			ShapeStyle = Enum.ParticleEmitterShapeStyle.Surface,
			Size = ns({ { 0, 1.5 }, { 0.5, 2.6 }, { 1, 0.3 } }),
			Speed = NumberRange.new(1, 3),
		})
		wisps.Enabled = true
		local full = s.Size
		local t0 = os.clock()
		local burstAt = cfg.BurstTime - cfg.ShellTime
		follow = RunService.RenderStepped:Connect(function()
			local t = os.clock() - t0
			local grow = math.clamp(t / 0.22, 0, 1)
			grow = 1 + 2.70158 * (grow - 1) ^ 3 + 1.70158 * (grow - 1) ^ 2 -- easeOutBack
			local pulse = 1 + 0.03 * math.sin(t * 7)
			local tremble = Vector3.zero
			if t > burstAt - 0.3 then
				local k = (t - (burstAt - 0.3)) / 0.3
				pulse += 0.05 * k
				tremble = Vector3.new(math.random() - 0.5, math.random() - 0.5, math.random() - 0.5) * 0.6 * k
			end
			s.Size = full * math.max(grow, 0.02) * pulse
			s.CFrame = CFrame.new(root.Position + Vector3.new(0, 0.2, 0) + tremble) * CFrame.Angles(0, t * 0.8, t * 0.3)
		end)
		if isLocal then
			CameraShake.Shake(0.5, 0.25)
		end
	end)
	cast:Delay(cfg.BurstTime, function()
		if follow then
			follow:Disconnect()
			follow = nil
		end
		local center = root.Position
		local s = shell
		shell = nil
		if s then
			local size0 = s.Size
			VFX.Animate(0.3, function(a)
				s.Size = size0 * (1 + 1.8 * VFX.outQuint(a))
				s.Transparency = a
				if a >= 1 then
					s:Destroy()
				end
			end)
		end
		local ground = Util.ground(center)
		local gpos = if ground then ground.Position else center - Vector3.new(0, 3, 0)
		VFX.Shockwave(CFrame.new(gpos + Vector3.new(0, 0.3, 0)), { Radius = cfg.Radius + 6, Duration = 0.5 })
		VFX.Burst(center, "Ink", 24)
		VFX.Burst(center, "Sparks", 30)
		local cam = workspace.CurrentCamera
		if cam then
			VFX.Shards(
				CFrame.lookAt(center, cam.CFrame.Position),
				{ Count = 16, MinLength = 4, MaxLength = 12, Offset = 3, Duration = 0.55, Seed = data.Seed }
			)
		end
		if ground then
			RockFX.Crater(gpos, {
				Ground = ground,
				Radius = 7,
				Count = 14,
				SizeMin = 1.6,
				SizeMax = 3,
				Duration = 2.5,
				Seed = data.Seed,
			})
			RockFX.Debris(gpos, {
				Ground = ground,
				Count = 16,
				UpMin = 35,
				UpMax = 70,
				OutMin = 15,
				OutMax = 40,
				Radius = 4,
				Seed = data.Seed,
			})
			VFX.GroundCracks(gpos + Vector3.new(0, 0.05, 0), 9, 7, 2.5, data.Seed)
		end
		SFX.Play("Boom", center)
		if nearby(center, isLocal) then
			CameraShake.ShakeAt(center, if isLocal then 2.2 else 1.6, 0.6, 140)
			ScreenFX.ImpactFrames(if isLocal then 0.8 else 0.5)
		end
		if isLocal then
			ScreenFX.FOVKick(12, 0.07, 0.5)
		end
	end)
end

-- --------------------------------------------------------------- BOYUT KESİĞİ

local function spawnSwirls(root: BasePart, cast, duration: number)
	local items = {}
	for k = 1, 2 do
		local mesh = VFX.Mesh("Swirl", 2.6 + k * 0.6)
		if mesh then
			mesh.Color = Config.Theme.Core
			table.insert(items, { part = mesh, speed = if k == 1 then 4 else -3, off = VFX.MeshOffset("Swirl") })
		end
	end
	local rings = {}
	if #items == 0 then -- fallback: dönen ince siyah halkalar (parçalardan)
		for k = 1, 3 do
			local segs = {}
			for s = 1, 10 do
				local p = VFX.Part({ Size = Vector3.new(0.25, 0.25, 1.6), Transparency = 0.2 })
				table.insert(segs, { part = p, a = s / 10 * math.pi * 2 })
			end
			table.insert(
				rings,
				{ segs = segs, r = 4 + k * 1.6, h = -1.5 + k * 1.2, speed = (if k % 2 == 0 then -1 else 1) * (3 + k) }
			)
		end
	end
	local t0 = os.clock()
	local conn = RunService.RenderStepped:Connect(function()
		local t = os.clock() - t0
		local grow = math.clamp(t / 0.5, 0, 1)
		for _, it in ipairs(items) do
			it.part.CFrame = CFrame.new(root.Position + Vector3.new(0, 0.5, 0))
				* CFrame.Angles(0, t * it.speed, 0)
				* it.off
			it.part.Transparency = 1 - 0.85 * grow
		end
		for _, ring in ipairs(rings) do
			for _, sg in ipairs(ring.segs) do
				local a = sg.a + t * ring.speed
				local r = ring.r * (0.6 + 0.4 * grow)
				local pos = root.Position
					+ Vector3.new(math.cos(a) * r, ring.h + math.sin(t * 3 + sg.a) * 0.3, math.sin(a) * r)
				sg.part.CFrame = CFrame.lookAt(pos, pos + Vector3.new(-math.sin(a), 0, math.cos(a)) * ring.speed)
				sg.part.Transparency = 1 - 0.8 * grow
			end
		end
	end)
	local function stop()
		conn:Disconnect()
		for _, it in ipairs(items) do
			VFX.FadeDestroy(it.part, 0.15)
		end
		for _, ring in ipairs(rings) do
			for _, sg in ipairs(ring.segs) do
				VFX.FadeDestroy(sg.part, 0.15)
			end
		end
	end
	task.delay(duration, stop)
	cast:OnCancel(stop)
end

local function cutWave(origin: Vector3, dir: Vector3, length: number, speed: number)
	local proj = VFX.CrescentProjectile(10)
	local ground = Util.ground(origin)
	local y = if ground then ground.Position.Y else origin.Y - 3
	local t0 = os.clock()
	local conn: RBXScriptConnection
	conn = RunService.RenderStepped:Connect(function()
		local dist = (os.clock() - t0) * speed
		if dist >= length then
			conn:Disconnect()
			proj:Destroy()
			return
		end
		local p = Vector3.new(origin.X, y + 1, origin.Z) + dir * (dist + 4)
		local fade = math.clamp((dist - length * 0.7) / (length * 0.3), 0, 1)
		proj:Set(CFrame.lookAt(p, p + dir) * CFrame.Angles(0, 0, math.rad(90)) * CFrame.new(0, 0, 7), fade)
	end)
end

local function DimensionSlash(cast, char: Model, data, isLocal: boolean)
	local cfg = Config.Skills.DimensionSlash
	local root = Util.getRoot(char)
	if root == nil then
		return
	end
	local dir = Util.flat(data.Dir) or Util.flat(root.CFrame.LookVector) or Vector3.zAxis
	local seed = tonumber(data.Seed) or 1
	local near = nearby(root.Position, isLocal)
	cast.anim = AnimPlayer.Play(char, cfg.Animation, isLocal, { FadeTime = 0.12 })
	if isLocal then
		lockRotation(char, cfg.Lock)
	end

	-- ============ ŞARJ
	local darken = if near then ScreenFX.Darken(if isLocal then 1 else 0.55, 0.9) else nil
	local rumble = if near
		then CameraShake.Rumble(if isLocal then 0.18 else 0.1, {
			Roughness = 10,
			Position = Vector3.new(0.12, 0.12, 0.08),
			Rotation = Vector3.new(0.45, 0.35, 0.6),
			FadeIn = 0.6,
		})
		else nil
	local chargeSound = SFX.Play("Charge", root)
	local aura = VFX.Aura(root, "Wisps", {
		Rate = 60,
		Size = ns({ { 0, 1.6 }, { 0.5, 2.6 }, { 1, 0.3 } }),
		Speed = NumberRange.new(2, 6),
		SpreadAngle = Vector2.new(70, 70),
		Lifetime = NumberRange.new(0.5, 0.9),
	})
	local embers =
		VFX.Aura(root, "Embers", { Rate = 35, SpreadAngle = Vector2.new(180, 180), Speed = NumberRange.new(4, 9) })
	local b = blade(char)
	local bladeAura = if b then VFX.Aura(b, "Wisps", { Rate = 70 }) else nil
	spawnSwirls(root, cast, cfg.SlashTime)
	local lev = nil
	cast:Delay(0.2, function()
		lev = RockFX.Levitate(root.Position, {
			Count = 16,
			Seed = seed,
			RadiusMin = 6,
			RadiusMax = 15,
			HeightMin = 2,
			HeightMax = 8,
			RiseTime = 0.9,
		})
	end)
	cast:Delay(0.3, function()
		local g = Util.ground(root.Position)
		if g then
			VFX.GroundCracks(g.Position + Vector3.new(0, 0.05, 0), 10, 9, 2.6, seed)
			VFX.Shockwave(CFrame.new(g.Position + Vector3.new(0, 0.2, 0)), { Radius = 10, Duration = 0.6 })
		end
	end)
	if rumble then
		cast:Delay(0.6, function()
			rumble:SetMagnitude(if isLocal then 0.35 else 0.18)
		end)
		cast:Delay(0.95, function()
			rumble:SetMagnitude(if isLocal then 0.6 else 0.3)
		end)
	end
	if isLocal then
		ScreenFX.FOVKick(-9, cfg.SlashTime - 0.05, 0.2)
	end
	local function endCharge()
		aura.Enabled = false
		embers.Enabled = false
		Debris:AddItem(aura, 1.2)
		Debris:AddItem(embers, 1.5)
		if bladeAura then
			bladeAura.Enabled = false
			Debris:AddItem(bladeAura, 1)
		end
		if rumble then
			rumble:Stop(0.15)
		end
		if darken then
			darken:Release(1.4)
		end
		SFX.FadeOut(chargeSound, 0.2)
	end
	cast:OnCancel(function()
		endCharge()
		if lev then
			lev:Drop()
		end
	end)
	enableTrail(cast, char, cfg.SlashTime - 0.06, 0.4)

	-- ============ KESİK
	cast:Delay(cfg.SlashTime, function()
		endCharge()
		local origin = root.Position
		local basis = CFrame.lookAt(origin, origin + dir)
		VFX.Crescent(
			basis * CFrame.new(0, 0.6, 0),
			{ Radius = 9.5, Roll = 180, Sweep = 85, Duration = 0.34, Grow = 1.35, Width = 1.3 }
		)

		-- uzayı kesen yarık
		local riftCF = basis * CFrame.new(0, 3, -cfg.RiftDistance) * CFrame.Angles(0, 0, math.rad(cfg.RiftTilt))
		local rift = VFX.Rift(riftCF, { Length = cfg.RiftLength, Open = 7.5, OpenTime = 0.07 })
		VFX.Shards(riftCF, {
			Count = 36,
			SpreadX = cfg.RiftLength * 0.8,
			MinLength = 4,
			MaxLength = 16,
			Vertical = true,
			Offset = 2.5,
			Duration = 0.9,
			Seed = seed,
		})
		-- yarıktan sızan karanlık
		local leaks = {}
		for k = -2, 2 do
			local a = VFX.Attachment(riftCF * CFrame.new(k * cfg.RiftLength * 0.18, 0, 0))
			local e = VFX.Emitter(a, "Smoke", {
				Rate = 30,
				Speed = NumberRange.new(2, 6),
				Lifetime = NumberRange.new(0.8, 1.4),
				Size = ns({ { 0, 3 }, { 1, 9 } }),
				Acceleration = Vector3.new(0, -2, 0),
			})
			table.insert(leaks, { a = a, e = e })
		end
		task.delay(cfg.RiftOpenTime, function()
			for _, l in ipairs(leaks) do
				l.e.Enabled = false
				Debris:AddItem(l.a, 1.5)
			end
		end)

		-- yerin yarılıp havalanması
		local g0 = Util.ground(origin)
		RockFX.Line(origin + dir * 4, dir, cfg.Length, {
			Seed = seed,
			Speed = cfg.WaveSpeed,
			Spacing = 4.5,
			Width = 3.4,
			SizeMin = 2.2,
			SizeMax = 5.2,
			Duration = 3,
			DebrisEvery = 2,
			DebrisCount = 5,
			UpMin = 55,
			UpMax = 115,
		})
		if g0 then
			VFX.GroundScar(g0.Position + dir * 3, g0.Position + dir * cfg.Length, 1.6, 3.4, g0.Position.Y)
			VFX.Shockwave(CFrame.new(g0.Position + Vector3.new(0, 0.3, 0)), { Radius = 30, Duration = 0.55 })
			RockFX.Crater(
				g0.Position,
				{ Ground = g0, Radius = 6, Count = 12, SizeMin = 1.4, SizeMax = 2.6, Duration = 2.6, Seed = seed }
			)
		end
		cutWave(origin, dir, cfg.Length, cfg.WaveSpeed)
		if lev then
			lev:Blast(dir, 1.35)
		end
		VFX.Burst(origin, "Ink", 20)

		-- ekran
		if near then
			ScreenFX.ImpactFrames(if isLocal then 1 else 0.7)
			ScreenFX.ScreenSlash(-cfg.RiftTilt, 0.3)
			CameraShake.Shake(if isLocal then 3.2 else 2.0, 1.05, { Roughness = 22 })
			ScreenFX.FOVKick(if isLocal then 20 else 9, 0.07, 0.65)
			ScreenFX.Monochrome(0.22, 0.9)
		end
		SFX.Play("Rift", riftCF.Position, { MaxDistance = 600 })
		SFX.Play("Boom", origin)

		task.delay(cfg.RiftOpenTime, function()
			rift:Close(0.26)
			if near then
				CameraShake.ShakeAt(riftCF.Position, 0.9, 0.35, 260)
			end
		end)
	end)
end

-- ------------------------------------------------------------------ KARA KILIÇ

local function BlackBlade(cast, char: Model, _data, isLocal: boolean)
	local cfg = Config.Skills.BlackBlade
	local root = Util.getRoot(char)
	if root == nil then
		return
	end
	cast.anim = AnimPlayer.Play(char, cfg.Animation, isLocal)
	local b = blade(char)
	if b then
		local e = VFX.Aura(b, "Wisps", { Rate = 100 })
		local function off()
			e.Enabled = false
			Debris:AddItem(e, 1)
		end
		task.delay(cfg.CoatTime + 0.25, off)
		cast:OnCancel(off)
	end
	SFX.Play("Coat", root)
	cast:Delay(cfg.CoatTime, function()
		local p = if b then b.Position else root.Position
		VFX.Burst(p, "Ink", 10)
		VFX.Burst(p, "Sparks", 16)
		local g = Util.ground(root.Position)
		if g then
			VFX.Shockwave(CFrame.new(g.Position + Vector3.new(0, 0.2, 0)), { Radius = 11, Duration = 0.4 })
		end
		if isLocal then
			CameraShake.Shake(0.6, 0.25)
			ScreenFX.FOVKick(6, 0.06, 0.3)
		end
	end)
end

-- ---------------------------------------------------------------------- EQUIP

local function Equip(cast, char: Model, _data, isLocal: boolean)
	cast.anim = AnimPlayer.Play(char, "Equip", isLocal, { FadeTime = 0.05 })
	local root = Util.getRoot(char)
	cast:Delay(Config.EquipGrabTime, function()
		SFX.Play("Draw", root)
		local b = blade(char)
		if b then
			VFX.Burst(b.Position, "Smoke", 5, { Size = ns({ { 0, 0.8 }, { 1, 2.5 } }) })
		end
	end)
	enableTrail(cast, char, Config.EquipGrabTime + 0.02, 0.25)
end

local HANDLERS = {
	M1 = M1,
	BlackMoon = BlackMoon,
	DeathThrust = DeathThrust,
	BlackCocoon = BlackCocoon,
	DimensionSlash = DimensionSlash,
	BlackBlade = BlackBlade,
	Equip = Equip,
}

function SkillFX.Play(skill: string, character: Model, data: { [string]: any }?, isLocal: boolean)
	local handler = HANDLERS[skill]
	local cast = Cast.new(character)
	if handler then
		local ok, err = pcall(handler, cast, character, data or {}, isLocal)
		if not ok then
			warn("[YamiSkills] FX hatası", skill, err)
		end
	end
	return cast
end

-- -------------------------------------------------------------------- darbeler

local HEAVY = { BlackMoon = true, DeathThrust = true, BlackCocoon = true, DimensionSlash = true }

function SkillFX.Hit(skill: string, attacker: Model?, victims: { Model }, data: { [string]: any }?)
	local d = data or {}
	local me = localCharacter()
	local aRoot = attacker and Util.getRoot(attacker)
	local heavy = HEAVY[skill] == true or (skill == "M1" and d.Index == 4)
	for _, v in ipairs(victims) do
		local vr = typeof(v) == "Instance" and Util.getRoot(v)
		if vr then
			local pos = vr.Position + Vector3.new(0, 0.5, 0)
			local from = if aRoot then aRoot.Position else pos - Vector3.zAxis
			local dir = Util.flat(pos - from) or Vector3.zAxis
			VFX.ImpactStar(pos - dir * 0.6, if heavy then 6.5 else 4)
			VFX.Burst(pos, "Sparks", if heavy then 24 else 12)
			VFX.Burst(pos, "Smoke", if heavy then 8 else 4, { Speed = NumberRange.new(6, 14) })
			if heavy then
				VFX.Burst(pos, "Ink", 6)
				VFX.Shockwave(
					CFrame.lookAt(pos, pos + dir) * CFrame.Angles(-math.pi / 2, 0, 0),
					{ Radius = 7, Duration = 0.3 }
				)
			end
			if skill == "DeathThrust" then -- delip geçen karanlık mızrak
				local spear = VFX.Part({
					Size = Vector3.new(0.5, 0.5, 14),
					CFrame = CFrame.lookAt(pos + dir * 6, pos + dir * 13),
				})
				VFX.Outline(spear, 0.3)
				VFX.Animate(0.35, function(a)
					spear.Size = Vector3.new(0.5 * (1 - a) + 0.05, 0.5 * (1 - a) + 0.05, 14 + 6 * a)
					spear.Transparency = a
					if a >= 1 then
						spear:Destroy()
					end
				end)
			elseif skill == "DimensionSlash" then -- kurbanın üzerinden geçen kesik çizgisi
				local cut = VFX.Part({
					Size = Vector3.new(9, 0.25, 0.25),
					CFrame = CFrame.lookAt(pos, pos + dir)
						* CFrame.Angles(0, 0, math.rad(Config.Skills.DimensionSlash.RiftTilt)),
				})
				VFX.Outline(cut, 0.1)
				VFX.Animate(0.5, function(a)
					cut.Size = Vector3.new(9 + 4 * a, 0.25 * (1 - a) + 0.03, 0.25)
					cut.Transparency = a ^ 2
					if a >= 1 then
						cut:Destroy()
					end
				end)
			end
			SFX.Play(if heavy then "HeavyHit" else "Hit", vr)
			if v == me then
				CameraShake.Shake(if heavy then 1.8 else 0.7, if heavy then 0.45 else 0.25)
				ScreenFX.Vignette(if heavy then 0.75 else 0.45, if heavy then 0.4 else 0.2)
			end
		end
	end
	if attacker ~= nil and attacker == me and #victims > 0 then
		CameraShake.Shake(if heavy then 0.9 else 0.35, 0.18, { Roughness = 25 })
	end
end

-- -------------------------------------------------------- Kara Kılıç (kalıcı aura)

local coatFx: { [Model]: { [string]: Instance } } = setmetatable({}, { __mode = "k" }) :: any

local function removeCoat(char: Model)
	local fx = coatFx[char]
	if fx == nil then
		return
	end
	coatFx[char] = nil
	for _, inst in pairs(fx) do
		if inst:IsA("ParticleEmitter") then
			inst.Enabled = false
			Debris:AddItem(inst, 1)
		else
			inst:Destroy()
		end
	end
	local t = trail(char)
	if t then
		t.Enabled = false
	end
end

function SkillFX.SetBlackBlade(character: Model, untilServerTime: number?)
	blackBladeUntil[character] = untilServerTime
	local now = workspace:GetServerTimeNow()
	if untilServerTime == nil or untilServerTime <= now then
		removeCoat(character)
		return
	end
	if coatFx[character] == nil then
		local m = katana(character)
		local b = blade(character)
		if m and b then
			local fx = {}
			fx.wisps = VFX.Aura(b, "Wisps", { Rate = 45 })
			fx.embers = VFX.Aura(b, "Embers", { Rate = 18 })
			local h = Instance.new("Highlight")
			h.Name = "YamiBlackBlade"
			h.Adornee = m
			h.FillColor = Config.Theme.Core
			h.FillTransparency = 0
			h.OutlineColor = Config.Theme.Accent
			h.OutlineTransparency = math.clamp(Config.Theme.OutlineTransparency + 0.2, 0, 1)
			h.DepthMode = Enum.HighlightDepthMode.Occluded
			h.Parent = m
			fx.highlight = h
			coatFx[character] = fx
			local t = trail(character)
			if t then
				t.Enabled = true
			end
		end
	end
	task.delay(untilServerTime - now + 0.05, function()
		local u = blackBladeUntil[character]
		if u == nil or u <= workspace:GetServerTimeNow() then
			removeCoat(character)
		end
	end)
end

return SkillFX
