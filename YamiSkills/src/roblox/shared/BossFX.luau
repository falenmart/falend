--[[
	BossFX (client) - Kızıl Kemik İblisi'nin animasyonları, saldırı efektleri ve can barı.
	Animasyonlar Blender'dan (Boss_Idle, Boss_Walk, Boss_Slash, Boss_Slam, Boss_Lunge, Boss_Roar,
	Boss_Death) her client'ta yerel oynatılır; yürürken/dururken otomatik geçiş yapılır.
]]
local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local Shared = script.Parent
local Config = require(Shared:WaitForChild("Config"))
local Util = require(Shared:WaitForChild("Util"))
local AnimPlayer = require(Shared:WaitForChild("AnimPlayer"))
local VFX = require(Shared:WaitForChild("VFX"))
local RockFX = require(Shared:WaitForChild("RockFX"))
local CameraShake = require(Shared:WaitForChild("CameraShake"))
local ScreenFX = require(Shared:WaitForChild("ScreenFX"))
local SFX = require(Shared:WaitForChild("SFX"))

local BossFX = {}

local cfg = Config.Boss
local RED = cfg.Colors.Red
local WHITE = cfg.Colors.White
local ns = VFX.ns

type BossState = { model: Model, loco: any, locoName: string?, dead: boolean }
local bosses: { [Model]: BossState } = {}

local function root(model: Model): BasePart?
	return model.PrimaryPart or Util.getRoot(model)
end

-- ------------------------------------------------------------- yardımcılar

local function telegraph(center: Vector3, radius: number, duration: number)
	local disc = VFX.Part({
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(0.12, radius * 2, radius * 2),
		CFrame = CFrame.new(center + Vector3.new(0, 0.12, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		Color = RED,
		Transparency = 0.75,
	})
	local ring = VFX.Part({
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(0.14, 0.1, 0.1),
		CFrame = disc.CFrame,
		Color = WHITE,
		Transparency = 0.35,
	})
	VFX.Animate(duration, function(a)
		local s = radius * 2 * a
		ring.Size = Vector3.new(0.14, math.max(s, 0.1), math.max(s, 0.1))
		disc.Transparency = 0.55 + 0.2 * math.sin(a * 30)
		if a >= 1 then
			disc:Destroy()
			ring:Destroy()
		end
	end)
end

local function spikes(center: Vector3, radius: number, seed: number)
	local ground = Util.ground(center)
	local base = if ground then ground.Position else center
	local rng = Random.new(seed)
	for i = 1, 9 do
		local ang = rng:NextNumber(0, math.pi * 2)
		local off = Vector3.new(math.cos(ang), 0, math.sin(ang)) * rng:NextNumber(0, radius * 0.8)
		local len = rng:NextNumber(5, 10)
		local p = VFX.Part({
			ClassName = "WedgePart",
			Size = Vector3.new(rng:NextNumber(0.8, 1.4), len, rng:NextNumber(1.2, 2)),
			Color = if i % 2 == 0 then WHITE else RED,
			Material = Enum.Material.SmoothPlastic,
		})
		local tilt = CFrame.Angles(rng:NextNumber(-0.35, 0.35), ang, rng:NextNumber(-0.35, 0.35))
		local shown = CFrame.new(base + off + Vector3.new(0, len * 0.42, 0)) * tilt
		local hidden = shown - Vector3.new(0, len, 0)
		p.CFrame = hidden
		p.CastShadow = true
		VFX.Tween(p, 0.1, { CFrame = shown }, Enum.EasingStyle.Back)
		task.delay(1.1 + rng:NextNumber(0, 0.3), function()
			local tw = VFX.Tween(p, 0.4, { CFrame = hidden }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
			tw.Completed:Connect(function()
				p:Destroy()
			end)
		end)
	end
	if ground then
		RockFX.Debris(base, { Ground = ground, Count = 5, UpMin = 30, UpMax = 55, Seed = seed })
	end
	VFX.Burst(base + Vector3.new(0, 1, 0), "Sparks", 14, { Color = ColorSequence.new(RED) })
	VFX.Shockwave(CFrame.new(base + Vector3.new(0, 0.3, 0)), { Radius = radius + 3, Duration = 0.35, Color = RED })
end

local function nearShake(pos: Vector3, mag: number, dur: number, radius: number?)
	CameraShake.ShakeAt(pos, mag, dur, radius or 110)
end

-- ----------------------------------------------------------------- saldırılar

local ATTACKS = {}

function ATTACKS.Slash(_model: Model, r: BasePart, data)
	local a = cfg.Attacks.Slash
	local dir = Util.flat(data.Dir) or Util.flat(r.CFrame.LookVector) or Vector3.zAxis
	task.delay(a.HitTime - 0.2, function()
		SFX.Play("HeavySwing", r, { Speed = 0.6, Volume = 1.4 })
	end)
	task.delay(a.HitTime - 0.05, function()
		if r.Parent == nil then
			return
		end
		local cf = CFrame.lookAt(r.Position + Vector3.new(0, 2.5, 0), r.Position + Vector3.new(0, 2.5, 0) + dir)
		VFX.Crescent(cf, { Radius = 14, Roll = 172, Sweep = 95, Duration = 0.38, Grow = 1.2, Width = 1.5, Color = RED })
		VFX.Crescent(
			cf * CFrame.new(0, 0.4, 0),
			{ Radius = 12, Roll = 172, Sweep = 95, Duration = 0.3, Grow = 1.15, Width = 0.6, Color = WHITE }
		)
		VFX.Burst(r.Position + dir * 8, "Sparks", 20, { Color = ColorSequence.new(RED) })
		nearShake(r.Position, 1.0, 0.35)
	end)
end

function ATTACKS.Slam(_model: Model, r: BasePart, data)
	local a = cfg.Attacks.Slam
	local impact: Vector3 = data.Impact or r.Position
	telegraph(impact, data.Radius or a.Radius, a.HitTime)
	task.delay(a.HitTime - 0.35, function()
		SFX.Play("HeavySwing", r, { Speed = 0.45, Volume = 1.4 })
	end)
	task.delay(a.HitTime, function()
		local ground = Util.ground(impact)
		local radius = data.Radius or a.Radius
		RockFX.Crater(
			impact,
			{
				Ground = ground,
				Radius = radius * 0.55,
				Count = 14,
				SizeMin = 2,
				SizeMax = 3.8,
				Duration = 3,
				Seed = data.Seed,
			}
		)
		RockFX.Debris(
			impact,
			{
				Ground = ground,
				Count = 16,
				UpMin = 40,
				UpMax = 80,
				OutMin = 15,
				OutMax = 40,
				Radius = 4,
				Seed = data.Seed,
			}
		)
		VFX.Shockwave(CFrame.new(impact + Vector3.new(0, 0.3, 0)), { Radius = radius + 8, Duration = 0.5, Color = RED })
		VFX.Shockwave(CFrame.new(impact + Vector3.new(0, 0.5, 0)), { Radius = radius, Duration = 0.4, Color = WHITE })
		VFX.GroundCracks(impact + Vector3.new(0, 0.05, 0), 10, radius * 0.8, 2.5, data.Seed)
		VFX.Burst(impact + Vector3.new(0, 1, 0), "Sparks", 30, { Color = ColorSequence.new(RED) })
		SFX.Play("Boom", impact, { Volume = 1.2 })
		nearShake(impact, 2.2, 0.6, 130)
		if ScreenFX.InRange(impact, 60) then
			ScreenFX.Flash(RED, 0.12, 0.25)
		end
	end)
end

function ATTACKS.Lunge(model: Model, r: BasePart, data)
	local a = cfg.Attacks.Lunge
	task.delay(0.15, function()
		VFX.Burst(
			r.Position - Vector3.new(0, 6, 0),
			"Dust",
			10,
			{ Color = ColorSequence.new(Color3.fromRGB(90, 84, 78)) }
		)
	end)
	task.delay(a.LungeTime, function()
		SFX.Play("Dash", r, { Speed = 0.6, Volume = 1.3 })
		for k = 0, 6 do
			task.delay(k * 0.05, function()
				if model.Parent then
					VFX.Afterimage(model, { Lifetime = 0.35, Transparency = 0.45, Color = RED })
				end
			end)
		end
		local dir = Util.flat(data.Dir) or Vector3.zAxis
		VFX.Shockwave(
			CFrame.lookAt(r.Position, r.Position + dir) * CFrame.Angles(-math.pi / 2, 0, 0),
			{ Radius = 12, Duration = 0.35, Color = RED }
		)
		nearShake(r.Position, 1.2, 0.4)
	end)
end

function ATTACKS.Roar(model: Model, r: BasePart, data)
	local a = cfg.Attacks.Roar
	local targets = if type(data.Targets) == "table" then data.Targets else {}
	local radius = data.SpikeRadius or a.SpikeRadius
	task.delay(0.25, function()
		for _, pos in ipairs(targets) do
			if typeof(pos) == "Vector3" then
				telegraph(pos, radius, a.BurstTime + a.SpikeDelay - 0.25)
			end
		end
	end)
	task.delay(a.BurstTime, function()
		if r.Parent == nil then
			return
		end
		local head = model:FindFirstChild("Head")
		local hp = if head and head:IsA("BasePart") then head.Position else r.Position + Vector3.new(0, 5, 0)
		local cam = workspace.CurrentCamera
		if cam then
			VFX.Shards(
				CFrame.lookAt(hp, cam.CFrame.Position),
				{ Count = 18, MinLength = 5, MaxLength = 14, Offset = 3, Duration = 0.7, Color = RED, Seed = data.Seed }
			)
		end
		local ground = Util.ground(r.Position)
		local gp = if ground then ground.Position else r.Position - Vector3.new(0, 8, 0)
		VFX.Shockwave(CFrame.new(gp + Vector3.new(0, 0.3, 0)), { Radius = 34, Duration = 0.7, Color = RED })
		VFX.Shockwave(CFrame.new(gp + Vector3.new(0, 0.5, 0)), { Radius = 24, Duration = 0.55, Color = WHITE })
		VFX.Burst(hp, "Sparks", 30, { Color = ColorSequence.new(RED) })
		SFX.Play("Rift", hp, { Volume = 0.9, Speed = 1.6 })
		if ScreenFX.InRange(r.Position, 90) then
			ScreenFX.Flash(RED, 0.18, 0.4)
			local rumble = CameraShake.Rumble(0.6, { Roughness = 14, FadeIn = 0.05 })
			task.delay(0.8, function()
				rumble:Stop(0.3)
			end)
		end
	end)
	task.delay(a.BurstTime + a.SpikeDelay, function()
		for i, pos in ipairs(targets) do
			if typeof(pos) == "Vector3" then
				spikes(pos, radius, (data.Seed or 1) + i)
				nearShake(pos, 1.0, 0.3, 60)
			end
		end
		SFX.Play("Boom", targets[1] or r.Position, { Volume = 0.7, Speed = 1.3 })
	end)
end

-- ------------------------------------------------------------------- can barı

local barGui: ScreenGui? = nil
local barFill: Frame? = nil
local barName: TextLabel? = nil
local barText: TextLabel? = nil

local function buildBar()
	local g = Instance.new("ScreenGui")
	g.Name = "YamiBossBar"
	g.ResetOnSpawn = false
	g.DisplayOrder = 15
	g.Enabled = false
	local frame = Instance.new("Frame")
	frame.AnchorPoint = Vector2.new(0.5, 0)
	frame.Position = UDim2.new(0.5, 0, 0, 46)
	frame.Size = UDim2.new(0, 460, 0, 20)
	frame.BackgroundColor3 = Color3.fromRGB(12, 4, 6)
	frame.BackgroundTransparency = 0.15
	frame.Parent = g
	Instance.new("UICorner", frame).CornerRadius = UDim.new(0, 4)
	local stroke = Instance.new("UIStroke")
	stroke.Color = WHITE
	stroke.Transparency = 0.3
	stroke.Parent = frame
	local fill = Instance.new("Frame")
	fill.Size = UDim2.fromScale(1, 1)
	fill.BackgroundColor3 = RED
	fill.BorderSizePixel = 0
	fill.Parent = frame
	Instance.new("UICorner", fill).CornerRadius = UDim.new(0, 4)
	local name = Instance.new("TextLabel")
	name.BackgroundTransparency = 1
	name.AnchorPoint = Vector2.new(0.5, 1)
	name.Position = UDim2.new(0.5, 0, 0, -2)
	name.Size = UDim2.new(1, 0, 0, 22)
	name.Font = Enum.Font.GothamBlack
	name.TextColor3 = WHITE
	name.TextStrokeTransparency = 0.3
	name.TextSize = 18
	name.Text = cfg.Name
	name.Parent = frame
	local txt = Instance.new("TextLabel")
	txt.BackgroundTransparency = 1
	txt.Size = UDim2.fromScale(1, 1)
	txt.Font = Enum.Font.GothamBold
	txt.TextColor3 = WHITE
	txt.TextStrokeTransparency = 0.4
	txt.TextSize = 13
	txt.ZIndex = 2
	txt.Parent = frame
	g.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")
	barGui, barFill, barName, barText = g, fill, name, txt
end

local function updateBar()
	if barGui == nil then
		return
	end
	local cam = workspace.CurrentCamera
	local best: Model? = nil
	local bestD = 170
	for model, st in pairs(bosses) do
		local r = root(model)
		local hum = model:FindFirstChildOfClass("Humanoid")
		if r and hum and not st.dead and cam then
			local d = (r.Position - cam.CFrame.Position).Magnitude
			if d < bestD then
				best, bestD = model, d
			end
		end
	end
	local g = barGui :: ScreenGui
	g.Enabled = best ~= nil
	if best then
		local hum = best:FindFirstChildOfClass("Humanoid") :: Humanoid
		local frac = math.clamp(hum.Health / math.max(hum.MaxHealth, 1), 0, 1)
		local fill = barFill :: Frame
		fill.Size = fill.Size:Lerp(UDim2.fromScale(frac, 1), 0.2);
		(barText :: TextLabel).Text = string.format("%d / %d", math.ceil(hum.Health), hum.MaxHealth);
		(barName :: TextLabel).Text = best.Name
	end
end

-- ------------------------------------------------------------------ takip

local function addBoss(model: Instance)
	if not model:IsA("Model") or bosses[model] then
		return
	end
	local st: BossState = { model = model, loco = nil, locoName = nil, dead = false }
	bosses[model] = st
	task.spawn(function()
		local crown = model:WaitForChild("Crown", 10)
		if crown and crown:IsA("BasePart") then
			VFX.Aura(
				crown,
				"Embers",
				{ Color = ColorSequence.new(RED), Rate = 22, LightEmission = 0.6, Size = ns({ { 0, 0.5 }, { 1, 0 } }) }
			)
		end
		local pelvis = model:WaitForChild("Pelvis", 10)
		if pelvis and pelvis:IsA("BasePart") then
			VFX.Aura(
				pelvis,
				"Wisps",
				{
					Rate = 14,
					Color = ColorSequence.new(Color3.fromRGB(40, 4, 10)),
					Size = ns({ { 0, 2 }, { 0.5, 3.5 }, { 1, 0.5 } }),
				}
			)
		end
		local head = model:WaitForChild("Head", 10)
		if head and head:IsA("BasePart") then
			local light = Instance.new("PointLight")
			light.Color = RED
			light.Range = 14
			light.Brightness = 2
			light.Parent = head
		end
	end)
end

local function removeBoss(model: Instance)
	bosses[model :: Model] = nil
end

local function stepBosses()
	for model, st in pairs(bosses) do
		if model.Parent == nil then
			bosses[model] = nil
			continue
		end
		if st.dead then
			continue
		end
		local r = root(model)
		if r == nil then
			continue
		end
		local v = r.AssemblyLinearVelocity
		local speed = Vector3.new(v.X, 0, v.Z).Magnitude
		local want = if speed > 1.5 then "Boss_Walk" else "Boss_Idle"
		if want ~= st.locoName then
			if st.loco then
				st.loco:Stop(0.3)
			end
			st.loco = AnimPlayer.Play(model, want, true, { FadeTime = 0.3 })
			st.locoName = want
		elseif want == "Boss_Walk" and st.loco then
			st.loco:AdjustSpeed(math.clamp(speed / cfg.WalkSpeed, 0.5, 1.6))
		end
	end
	updateBar()
end

function BossFX.Init(bossEvent: RemoteEvent)
	buildBar()
	for _, m in ipairs(CollectionService:GetTagged("YamiBoss")) do
		addBoss(m)
	end
	CollectionService:GetInstanceAddedSignal("YamiBoss"):Connect(addBoss)
	CollectionService:GetInstanceRemovedSignal("YamiBoss"):Connect(removeBoss)
	RunService.Heartbeat:Connect(stepBosses)

	bossEvent.OnClientEvent:Connect(function(kind: string, model: any, a: any, b: any)
		if typeof(model) ~= "Instance" or not model:IsA("Model") then
			return
		end
		addBoss(model)
		local r = root(model)
		if r == nil then
			return
		end
		if kind == "Attack" then
			local name, data = a, (b or {})
			AnimPlayer.Play(model, "Boss_" .. tostring(name), true, { FadeTime = 0.12 })
			local fn = ATTACKS[name]
			if fn then
				local ok, err = pcall(fn, model, r, data)
				if not ok then
					warn("[YamiSkills] Boss FX:", err)
				end
			end
		elseif kind == "Hit" then
			local victims = if type(b) == "table" then b else {}
			local me = Players.LocalPlayer.Character
			for _, v in ipairs(victims) do
				local vr = typeof(v) == "Instance" and Util.getRoot(v)
				if vr then
					VFX.ImpactStar(vr.Position, 5, RED)
					VFX.Burst(vr.Position, "Sparks", 16, { Color = ColorSequence.new(RED) })
					SFX.Play("HeavyHit", vr)
					if v == me then
						CameraShake.Shake(1.3, 0.35)
						ScreenFX.Vignette(0.6, 0.3)
					end
				end
			end
		elseif kind == "Death" then
			local st = bosses[model]
			if st then
				st.dead = true
				if st.loco then
					st.loco:Stop(0.2)
				end
			end
			AnimPlayer.Play(model, "Boss_Death", true, { FadeTime = 0.1, FadeOut = 3 })
			SFX.Play("Rift", r.Position, { Volume = 1.0, Speed = 0.8 })
			for k = 0, 5 do
				task.delay(k * 0.4, function()
					if model.Parent then
						VFX.Burst(
							r.Position + Vector3.new(0, 2, 0),
							"Ink",
							10,
							{ Color = ColorSequence.new(if k % 2 == 0 then RED else Color3.new(0, 0, 0)) }
						)
					end
				end)
			end
			task.delay(2.4, function()
				for _, d in ipairs(model:GetDescendants()) do
					if d:IsA("BasePart") and d.Transparency < 1 then
						TweenService:Create(d, TweenInfo.new(1.2), { Transparency = 1 }):Play()
					end
				end
				local g = Util.ground(r.Position)
				local gp = if g then g.Position else r.Position
				VFX.Shockwave(CFrame.new(gp + Vector3.new(0, 0.3, 0)), { Radius = 40, Duration = 0.8, Color = RED })
				nearShake(gp, 1.6, 0.6, 150)
			end)
		end
	end)
end

return BossFX
