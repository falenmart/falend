--[[
	RockFX (client) - zemin parçalanması / havalanma efektleri.
	Kayalar zeminin materyalini ve rengini alır (Terrain veya Part). Uçan enkaz sahte fizikle
	(çarpışmasız, oyuncuyu itmez) hesaplanır, bu yüzden hafif ve kararlıdır.

	Crater(center, opts)        : dışa doğru eğik kaya halkası
	Line(origin, dir, len, opts): ileri doğru sırayla yükselen kaya hendekleri (kesik dalgası)
	Debris(position, opts)      : havaya fırlayan taşlar
	Levitate(center, opts)      : yerden kopup havada süzülen kayalar -> handle:Blast(dir) / handle:Drop()
]]
local RunService = game:GetService("RunService")

local Shared = script.Parent
local Util = require(Shared:WaitForChild("Util"))
local VFX = require(Shared:WaitForChild("VFX"))

local RockFX = {}

local ROCK_MESHES = { "Rock1", "Rock2", "Rock3" }

local function makeRock(size: number, material: Enum.Material, color: Color3, rng: Random): BasePart
	local name = ROCK_MESHES[rng:NextInteger(1, 3)]
	local mesh = VFX.Mesh(name, size / 2)
	local p: BasePart
	if mesh then
		p = mesh
		mesh.TextureID = ""
	else
		p = VFX.Part({ Size = Vector3.new(size, size * rng:NextNumber(0.7, 1.1), size * rng:NextNumber(0.8, 1.2)) })
	end
	p.Material = material
	p.Color = color
	p.CastShadow = true
	return p
end

-- ------------------------------------------------------------ sahte fizik döngüsü

type Flying = {
	part: BasePart,
	vel: Vector3,
	spin: Vector3,
	groundY: number,
	bounces: number,
	age: number,
	life: number,
	half: number,
	settled: boolean,
	size0: Vector3,
}
local flying: { Flying } = {}
local conn: RBXScriptConnection? = nil
local GRAVITY = Vector3.new(0, -workspace.Gravity * 0.6, 0) -- biraz "anime" süzülmesi

local function stepFlying(dt: number)
	for i = #flying, 1, -1 do
		local f = flying[i]
		f.age += dt
		if f.part.Parent == nil then
			table.remove(flying, i)
			continue
		end
		if not f.settled then
			f.vel += GRAVITY * dt
			local cf = f.part.CFrame
			local pos = cf.Position + f.vel * dt
			local rot = cf.Rotation * CFrame.Angles(f.spin.X * dt, f.spin.Y * dt, f.spin.Z * dt)
			if pos.Y - f.half <= f.groundY and f.vel.Y < 0 then
				pos = Vector3.new(pos.X, f.groundY + f.half, pos.Z)
				if f.bounces > 0 and f.vel.Y < -12 then
					f.bounces -= 1
					f.vel = Vector3.new(f.vel.X * 0.55, -f.vel.Y * 0.32, f.vel.Z * 0.55)
					f.spin *= 0.5
				else
					f.settled = true
				end
			end
			f.part.CFrame = CFrame.new(pos) * rot
		end
		local remain = f.life - f.age
		if remain < 0.6 then
			local k = math.clamp(remain / 0.6, 0, 1)
			f.part.Size = f.size0 * math.max(k, 0.05)
			f.part.Transparency = 1 - k
			if remain <= 0 then
				f.part:Destroy()
				table.remove(flying, i)
			end
		end
	end
	if #flying == 0 and conn then
		conn:Disconnect()
		conn = nil
	end
end

local function launch(part: BasePart, vel: Vector3, spin: Vector3, groundY: number, life: number)
	table.insert(flying, {
		part = part,
		vel = vel,
		spin = spin,
		groundY = groundY,
		bounces = 2,
		age = 0,
		life = life,
		half = math.min(part.Size.X, part.Size.Y, part.Size.Z) * 0.45,
		settled = false,
		size0 = part.Size,
	})
	if conn == nil then
		conn = RunService.RenderStepped:Connect(stepFlying)
	end
end

-- ------------------------------------------------------------------- efektler

function RockFX.Debris(position: Vector3, opts: { [string]: any }?)
	local o = (opts or {}) :: any
	local ground = o.Ground or Util.ground(position)
	if ground == nil then
		return
	end
	local rng = Random.new(o.Seed or math.random(1, 1e6))
	local count = o.Count or 10
	local up0, up1 = o.UpMin or 35, o.UpMax or 70
	local out0, out1 = o.OutMin or 8, o.OutMax or 30
	local s0, s1 = o.SizeMin or 0.6, o.SizeMax or 1.6
	local dir = o.Direction -- isteğe bağlı yön eğilimi
	for _ = 1, count do
		local size = rng:NextNumber(s0, s1)
		local p = makeRock(size, ground.Material, ground.Color, rng)
		local spread = Util.randomUnitXZ(rng)
		if dir then
			spread = (spread * 0.6 + dir * 0.8).Unit
		end
		local start = ground.Position + spread * rng:NextNumber(0, o.Radius or 2) + Vector3.new(0, size * 0.3, 0)
		p.CFrame = CFrame.new(start)
			* CFrame.Angles(rng:NextNumber(0, 6.28), rng:NextNumber(0, 6.28), rng:NextNumber(0, 6.28))
		local vel = spread * rng:NextNumber(out0, out1) + Vector3.new(0, rng:NextNumber(up0, up1), 0)
		local spin = Vector3.new(rng:NextNumber(-9, 9), rng:NextNumber(-9, 9), rng:NextNumber(-9, 9))
		launch(p, vel, spin, ground.Position.Y, rng:NextNumber(o.LifeMin or 2.2, o.LifeMax or 3.6))
	end
	if o.Dust ~= false then
		VFX.Burst(ground.Position + Vector3.new(0, 1, 0), "Dust", o.DustCount or 8, {
			Color = ColorSequence.new(ground.Color),
		})
	end
end

-- Dışa eğik kaya halkası (krater)
function RockFX.Crater(center: Vector3, opts: { [string]: any }?)
	local o = (opts or {}) :: any
	local ground = o.Ground or Util.ground(center)
	if ground == nil then
		return
	end
	local rng = Random.new(o.Seed or math.random(1, 1e6))
	local count = o.Count or 12
	local radius = o.Radius or 8
	local s0, s1 = o.SizeMin or 1.6, o.SizeMax or 3
	local duration = o.Duration or 3
	local base = ground.Position
	for i = 1, count do
		local ang = (i / count) * math.pi * 2 + rng:NextNumber(-0.15, 0.15)
		local dir = Vector3.new(math.cos(ang), 0, math.sin(ang))
		local size = rng:NextNumber(s0, s1)
		local p = makeRock(size, ground.Material, ground.Color, rng)
		local pos = base + dir * (radius + rng:NextNumber(-0.8, 0.8))
		local tilt = CFrame.lookAt(pos, pos + dir)
			* CFrame.Angles(math.rad(rng:NextNumber(30, 55)), 0, math.rad(rng:NextNumber(-15, 15)))
		local hidden = tilt - Vector3.new(0, size * 1.1, 0)
		local shown = tilt + Vector3.new(0, size * 0.1, 0)
		p.CFrame = hidden
		VFX.Tween(p, 0.14, { CFrame = shown }, Enum.EasingStyle.Back)
		task.delay(duration + rng:NextNumber(0, 0.4), function()
			if p.Parent then
				local tw = VFX.Tween(p, 0.6, { CFrame = hidden }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
				tw.Completed:Connect(function()
					p:Destroy()
				end)
			end
		end)
	end
	if o.Dust ~= false then
		VFX.Burst(base + Vector3.new(0, 1, 0), "Dust", o.DustCount or 14, {
			Color = ColorSequence.new(ground.Color),
			Speed = NumberRange.new(radius * 1.5, radius * 3),
		})
	end
end

-- Kesik dalgası: origin'den dir yönünde length boyunca sırayla yükselen iki sıra kaya + enkaz
function RockFX.Line(origin: Vector3, dir: Vector3, length: number, opts: { [string]: any }?)
	local o = (opts or {}) :: any
	local rng = Random.new(o.Seed or math.random(1, 1e6))
	local spacing = o.Spacing or 4
	local width = o.Width or 3
	local speed = o.Speed or 200
	local duration = o.Duration or 3.2
	local s0, s1 = o.SizeMin or 2, o.SizeMax or 4.5
	local debrisEvery = o.DebrisEvery or 3
	local side = dir:Cross(Vector3.yAxis).Unit
	local n = math.floor(length / spacing)
	for i = 1, n do
		local dist = i * spacing
		task.delay(dist / speed, function()
			local center = origin + dir * dist
			local ground = Util.ground(center)
			if ground == nil then
				return
			end
			for _, sgn in ipairs({ -1, 1 }) do
				local size = rng:NextNumber(s0, s1) * (1 - 0.35 * dist / length)
				local p = makeRock(size, ground.Material, ground.Color, rng)
				local pos = ground.Position + side * sgn * (width + rng:NextNumber(-0.6, 0.8))
				local outward = side * sgn
				local tilt = CFrame.lookAt(pos, pos + outward)
					* CFrame.Angles(math.rad(rng:NextNumber(25, 50)), math.rad(rng:NextNumber(-20, 20)), 0)
				local hidden = tilt - Vector3.new(0, size * 1.1, 0)
				local shown = tilt + Vector3.new(0, size * 0.15, 0)
				p.CFrame = hidden
				VFX.Tween(p, 0.12, { CFrame = shown }, Enum.EasingStyle.Back)
				task.delay(duration + rng:NextNumber(0, 0.5), function()
					if p.Parent then
						local tw =
							VFX.Tween(p, 0.7, { CFrame = hidden }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
						tw.Completed:Connect(function()
							p:Destroy()
						end)
					end
				end)
			end
			if i % debrisEvery == 0 then
				RockFX.Debris(ground.Position, {
					Ground = ground,
					Seed = rng:NextInteger(1, 1e6),
					Count = o.DebrisCount or 4,
					UpMin = o.UpMin or 45,
					UpMax = o.UpMax or 95,
					OutMin = 4,
					OutMax = 16,
					SizeMin = 0.7,
					SizeMax = 2.2,
					DustCount = 3,
				})
			end
		end)
	end
end

-- Havada süzülen kayalar (şarj sırasında yer kopar)
function RockFX.Levitate(center: Vector3, opts: { [string]: any }?)
	local o = (opts or {}) :: any
	local rng = Random.new(o.Seed or math.random(1, 1e6))
	local count = o.Count or 14
	local r0, r1 = o.RadiusMin or 5, o.RadiusMax or 14
	local h0, h1 = o.HeightMin or 2, o.HeightMax or 9
	local riseTime = o.RiseTime or 0.9
	local rocks = {}
	for i = 1, count do
		local ang = (i / count) * math.pi * 2 + rng:NextNumber(-0.25, 0.25)
		local pos = center + Vector3.new(math.cos(ang), 0, math.sin(ang)) * rng:NextNumber(r0, r1)
		local ground = Util.ground(pos)
		if ground then
			local size = rng:NextNumber(o.SizeMin or 0.8, o.SizeMax or 2.4)
			local p = makeRock(size, ground.Material, ground.Color, rng)
			local rot = CFrame.Angles(rng:NextNumber(0, 6.28), rng:NextNumber(0, 6.28), rng:NextNumber(0, 6.28))
			local startPos = ground.Position - Vector3.new(0, size * 0.5, 0)
			local target = ground.Position + Vector3.new(0, rng:NextNumber(h0, h1), 0)
			p.CFrame = CFrame.new(startPos) * rot
			local entry =
				{ part = p, base = target, phase = rng:NextNumber(0, 6.28), groundY = ground.Position.Y, rot = rot }
			table.insert(rocks, entry)
			local delayT = rng:NextNumber(0, riseTime * 0.6)
			task.delay(delayT, function()
				VFX.Burst(
					ground.Position,
					"Dust",
					2,
					{ Color = ColorSequence.new(ground.Color), Speed = NumberRange.new(3, 8) }
				)
			end)
			entry.riseStart = os.clock() + delayT
		end
	end
	local alive = true
	local loop
	loop = RunService.RenderStepped:Connect(function()
		if not alive then
			loop:Disconnect()
			return
		end
		local now = os.clock()
		for _, e in ipairs(rocks) do
			if e.part.Parent then
				local a = math.clamp((now - e.riseStart) / (riseTime * 0.6), 0, 1)
				local ease = 1 - (1 - a) ^ 3
				local bob = math.sin(now * 2.2 + e.phase) * 0.35 * ease
				local from = Vector3.new(e.base.X, e.groundY - 0.5, e.base.Z)
				local pos = from:Lerp(e.base, ease) + Vector3.new(0, bob, 0)
				e.part.CFrame = CFrame.new(pos) * e.rot * CFrame.Angles(now * 0.4 + e.phase, now * 0.3, 0)
			end
		end
	end)
	local handle = {}
	-- Hepsini merkezden dışa / verilen yöne fırlat
	function handle.Blast(_, dir: Vector3?, power: number?)
		alive = false
		local pw = power or 1
		for _, e in ipairs(rocks) do
			if e.part.Parent then
				local away = Util.flat(e.part.Position - center) or Vector3.xAxis
				local d = if dir then (away * 0.5 + dir).Unit else away
				local vel = d * rng:NextNumber(30, 70) * pw + Vector3.new(0, rng:NextNumber(30, 60) * pw, 0)
				launch(
					e.part,
					vel,
					Vector3.new(rng:NextNumber(-10, 10), rng:NextNumber(-10, 10), rng:NextNumber(-10, 10)),
					e.groundY,
					rng:NextNumber(2.2, 3.4)
				)
			end
		end
	end
	function handle.Drop()
		alive = false
		for _, e in ipairs(rocks) do
			if e.part.Parent then
				launch(e.part, Vector3.new(0, -5, 0), Vector3.zero, e.groundY, 2)
			end
		end
	end
	return handle
end

return RockFX
