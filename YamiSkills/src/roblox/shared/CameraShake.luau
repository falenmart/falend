--[[
	CameraShake (client)
	Perlin gürültülü, üst üste binebilen kamera sarsıntısı. Kamera script'inden SONRA uygulanır
	(RenderPriority.Camera + 1) bu yüzden birikmez ve kamera kontrolünü bozmaz.

	CameraShake.Shake(magnitude, duration, opts)
	CameraShake.ShakeAt(position, magnitude, duration, radius, opts)  -- mesafeye göre zayıflar
	CameraShake.Rumble(magnitude) -> handle:SetMagnitude(m) / handle:Stop()  -- sürekli titreşim
]]
local RunService = game:GetService("RunService")

local Config = require(script.Parent:WaitForChild("Config"))

local CameraShake = {}

type Shake = {
	magnitude: number,
	roughness: number,
	duration: number,
	fadeIn: number,
	start: number,
	seed: number,
	pos: Vector3,
	rot: Vector3,
	sustain: boolean,
	stopped: boolean,
	stopTime: number,
	fadeOut: number,
}

local shakes: { Shake } = {}
local bound = false

local function noise3(t: number, seed: number): Vector3
	return Vector3.new(math.noise(t, seed, 0.31), math.noise(t, seed + 13.7, 0.57), math.noise(t, seed + 27.1, 0.83))
end

local function update()
	local cam = workspace.CurrentCamera
	if cam == nil or #shakes == 0 then
		return
	end
	local now = os.clock()
	local pos, rot = Vector3.zero, Vector3.zero
	for i = #shakes, 1, -1 do
		local s = shakes[i]
		local age = now - s.start
		local amp
		if s.sustain then
			amp = math.clamp(age / math.max(s.fadeIn, 1e-3), 0, 1)
			if s.stopped then
				local k = (now - s.stopTime) / math.max(s.fadeOut, 1e-3)
				if k >= 1 then
					table.remove(shakes, i)
					continue
				end
				amp *= 1 - k
			end
		else
			if age >= s.duration then
				table.remove(shakes, i)
				continue
			end
			if age < s.fadeIn then
				amp = age / s.fadeIn
			else
				local k = (age - s.fadeIn) / math.max(s.duration - s.fadeIn, 1e-3)
				amp = (1 - k) ^ 2
			end
		end
		amp *= s.magnitude
		local n = noise3(age * s.roughness, s.seed)
		pos += n * s.pos * amp
		rot += n * s.rot * amp
	end
	local m = Config.Screen.ShakeMultiplier
	cam.CFrame = cam.CFrame
		* CFrame.new(pos * m)
		* CFrame.Angles(math.rad(rot.X * m), math.rad(rot.Y * m), math.rad(rot.Z * m))
end

local function ensureBound()
	if not bound then
		bound = true
		RunService:BindToRenderStep("YamiCameraShake", Enum.RenderPriority.Camera.Value + 1, update)
	end
end

local function new(magnitude: number, duration: number, opts: any?): Shake
	opts = opts or {}
	return {
		magnitude = magnitude,
		roughness = opts.Roughness or 18,
		duration = duration,
		fadeIn = opts.FadeIn or 0.03,
		start = os.clock(),
		seed = math.random() * 1000,
		pos = opts.Position or Vector3.new(0.35, 0.35, 0.2),
		rot = opts.Rotation or Vector3.new(1.4, 1.1, 1.8),
		sustain = false,
		stopped = false,
		stopTime = 0,
		fadeOut = opts.FadeOut or 0.3,
	}
end

function CameraShake.Shake(magnitude: number, duration: number, opts: any?)
	if not Config.Screen.Shake or magnitude <= 0 then
		return
	end
	table.insert(shakes, new(magnitude, duration, opts))
	ensureBound()
end

function CameraShake.ShakeAt(position: Vector3, magnitude: number, duration: number, radius: number?, opts: any?)
	local cam = workspace.CurrentCamera
	if cam == nil then
		return
	end
	local r = radius or 120
	local d = (cam.CFrame.Position - position).Magnitude
	local k = 1 - math.clamp(d / r, 0, 1)
	if k > 0.02 then
		CameraShake.Shake(magnitude * k * k, duration, opts)
	end
end

function CameraShake.Rumble(magnitude: number, opts: any?)
	local s = new(magnitude, math.huge, opts)
	s.sustain = true
	s.fadeIn = (opts and opts.FadeIn) or 0.4
	if Config.Screen.Shake then
		table.insert(shakes, s)
		ensureBound()
	end
	local handle = {}
	function handle.SetMagnitude(_, m: number)
		s.magnitude = m
	end
	function handle.Stop(_, fade: number?)
		if not s.stopped then
			s.stopped = true
			s.stopTime = os.clock()
			s.fadeOut = fade or 0.3
		end
	end
	return handle
end

return CameraShake
