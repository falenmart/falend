--[[
	AnimPlayer (client)
	Blender'dan gelen KeyframeSequence animasyonlarını oynatır.

	* Config.AnimationIds[ad] doluysa -> normal Animator (Roblox otomatik çoğaltır / replicate).
	* Boşsa -> dahili oynatıcı: KeyframeSequence verisini okuyup her karede Motor6D.Transform'a
	  yazar (RunService.PreSimulation: Animator'dan SONRA, fizikten ÖNCE). Yükleme gerektirmez;
	  her client bu animasyonu ilgili karakter için kendisi oynatır.
]]
local RunService = game:GetService("RunService")

local Shared = script.Parent
local Config = require(Shared:WaitForChild("Config"))

local AnimPlayer = {}

local animFolder = Shared:WaitForChild("Animations")

type JointData = { times: { number }, cframes: { CFrame } }
type ClipData = { length: number, loop: boolean, priority: number, joints: { [string]: JointData } }

local compiled: { [string]: ClipData | false } = {}

local PRIORITY_BY_VALUE: { [number]: Enum.AnimationPriority } = {}
for _, item in ipairs(Enum.AnimationPriority:GetEnumItems()) do
	PRIORITY_BY_VALUE[item.Value] = item :: any
end

local function compile(name: string): ClipData?
	local cached = compiled[name]
	if cached ~= nil then
		return cached or nil
	end
	local kfs = animFolder:FindFirstChild(name)
	if kfs == nil or not kfs:IsA("KeyframeSequence") then
		warn("[YamiSkills] KeyframeSequence bulunamadı:", name)
		compiled[name] = false
		return nil
	end
	local data: ClipData = { length = 0, loop = kfs.Loop, priority = kfs.Priority.Value, joints = {} }
	local keyframes = kfs:GetKeyframes()
	table.sort(keyframes, function(a, b)
		return (a :: Keyframe).Time < (b :: Keyframe).Time
	end)
	for _, kf in ipairs(keyframes) do
		local keyframe = kf :: Keyframe
		data.length = math.max(data.length, keyframe.Time)
		for _, pose in ipairs(keyframe:GetDescendants()) do
			if pose:IsA("Pose") and pose.Weight > 0 then
				local j = data.joints[pose.Name]
				if j == nil then
					j = { times = {}, cframes = {} }
					data.joints[pose.Name] = j
				end
				table.insert(j.times, keyframe.Time)
				table.insert(j.cframes, pose.CFrame)
			end
		end
	end
	compiled[name] = data
	return data
end

local function sample(j: JointData, t: number): CFrame
	local times = j.times
	local n = #times
	if t <= times[1] then
		return j.cframes[1]
	end
	if t >= times[n] then
		return j.cframes[n]
	end
	local lo, hi = 1, n
	while hi - lo > 1 do
		local mid = (lo + hi) // 2
		if times[mid] <= t then
			lo = mid
		else
			hi = mid
		end
	end
	local t0, t1 = times[lo], times[hi]
	local a = if t1 > t0 then (t - t0) / (t1 - t0) else 0
	return j.cframes[lo]:Lerp(j.cframes[hi], a)
end

-- ------------------------------------------------------------------ Animator yolu
function AnimPlayer.HasUploaded(name: string): boolean
	local id = Config.AnimationIds[name]
	return type(id) == "string" and id ~= "" and id ~= "rbxassetid://" and id ~= "rbxassetid://0"
end

local animatorTracks: { [Animator]: { [string]: AnimationTrack } } = setmetatable({}, { __mode = "k" }) :: any

local function getAnimator(character: Model): Animator?
	local hum = character:FindFirstChildOfClass("Humanoid")
	if hum == nil then
		return nil
	end
	local animator = hum:FindFirstChildOfClass("Animator")
	if animator == nil then
		animator = Instance.new("Animator")
		animator.Parent = hum
	end
	return animator
end

local function getTrack(animator: Animator, name: string): AnimationTrack?
	local cache = animatorTracks[animator]
	if cache == nil then
		cache = {}
		animatorTracks[animator] = cache
	end
	local track = cache[name]
	if track then
		return track
	end
	local anim = Instance.new("Animation")
	anim.Name = name
	anim.AnimationId = Config.AnimationIds[name]
	local ok, result = pcall(function()
		return animator:LoadAnimation(anim)
	end)
	if not ok then
		warn("[YamiSkills] Animasyon yüklenemedi:", name, result)
		return nil
	end
	track = result :: AnimationTrack
	local clip = compile(name)
	if clip then
		track.Priority = PRIORITY_BY_VALUE[clip.priority] or Enum.AnimationPriority.Action
		track.Looped = clip.loop
	end
	cache[name] = track
	return track
end

-- ------------------------------------------------------------------ dahili oynatıcı
type Track = {
	name: string,
	data: ClipData,
	start: number,
	speed: number,
	fadeIn: number,
	fadeOut: number,
	stopAt: number?,
	weight: number,
}
type CharState = { tracks: { Track }, motors: { [string]: Motor6D } }

local active: { [Model]: CharState } = {}
local loopConn: RBXScriptConnection? = nil

local function findMotors(character: Model): { [string]: Motor6D }
	local motors = {}
	for _, d in ipairs(character:GetDescendants()) do
		if d:IsA("Motor6D") and d.Part1 then
			motors[d.Part1.Name] = d
		end
	end
	return motors
end

local function step()
	local now = os.clock()
	for character, st in pairs(active) do
		if character.Parent == nil then
			active[character] = nil
			continue
		end
		table.sort(st.tracks, function(a, b)
			if a.data.priority ~= b.data.priority then
				return a.data.priority < b.data.priority
			end
			return a.start < b.start
		end)
		local i = 1
		while i <= #st.tracks do
			local tr = st.tracks[i]
			local data = tr.data
			local elapsed = now - tr.start
			local t = elapsed * tr.speed
			local w = tr.weight
			if tr.fadeIn > 0 then
				w *= math.clamp(elapsed / tr.fadeIn, 0, 1)
			end
			if data.loop then
				if data.length > 0 then
					t = t % data.length
				end
			elseif t >= data.length then
				t = data.length
				if tr.stopAt == nil then
					tr.stopAt = tr.start + data.length / math.max(tr.speed, 1e-3)
				end
			end
			local finished = false
			if tr.stopAt then
				local k = (now - tr.stopAt) / math.max(tr.fadeOut, 1e-3)
				if k >= 1 then
					finished = true
				elseif k > 0 then
					w *= 1 - k
				end
			end
			if finished then
				table.remove(st.tracks, i)
			else
				for partName, joint in pairs(data.joints) do
					local motor = st.motors[partName]
					if motor == nil or motor.Parent == nil then
						st.motors = findMotors(character)
						motor = st.motors[partName]
					end
					if motor then
						local cf = sample(joint, t)
						if w >= 0.999 then
							motor.Transform = cf
						elseif w > 0 then
							motor.Transform = motor.Transform:Lerp(cf, w)
						end
					end
				end
				i += 1
			end
		end
		if #st.tracks == 0 then
			active[character] = nil
		end
	end
	if next(active) == nil and loopConn then
		loopConn:Disconnect()
		loopConn = nil
	end
end

local function ensureLoop()
	if loopConn == nil then
		loopConn = RunService.PreSimulation:Connect(step)
	end
end

export type Handle = { Stop: (self: Handle, fadeTime: number?) -> (), AdjustSpeed: (self: Handle, speed: number) -> () }

local function playFallback(character: Model, name: string, opts): Handle?
	local data = compile(name)
	if data == nil then
		return nil
	end
	local st = active[character]
	if st == nil then
		st = { tracks = {}, motors = findMotors(character) }
		active[character] = st
	end
	for _, other in ipairs(st.tracks) do -- aynı animasyon tekrar başlarsa eskisini yumuşakça bitir
		if other.name == name and other.stopAt == nil then
			other.stopAt = os.clock()
			other.fadeOut = 0.08
		end
	end
	local tr: Track = {
		name = name,
		data = data,
		start = os.clock(),
		speed = opts.Speed or 1,
		fadeIn = opts.FadeTime or 0.08,
		fadeOut = opts.FadeOut or 0.18,
		stopAt = nil,
		weight = opts.Weight or 1,
	}
	table.insert(st.tracks, tr)
	ensureLoop()
	local handle = {}
	function handle.Stop(_, fadeTime: number?)
		if tr.stopAt == nil or tr.stopAt > os.clock() then
			tr.stopAt = os.clock()
			tr.fadeOut = fadeTime or 0.15
		end
	end
	function handle.AdjustSpeed(_, speed: number)
		local now = os.clock()
		local t = (now - tr.start) * tr.speed
		tr.speed = speed
		tr.start = now - t / math.max(speed, 1e-3)
	end
	return handle :: any
end

--[[
	Play(character, name, isLocalCharacter, opts)
	isLocalCharacter: bu client'ın kendi karakteri mi? Yüklenmiş (ID'li) animasyonlar zaten
	Animator ile herkese çoğaltıldığı için başkalarının karakterinde tekrar oynatılmaz.
]]
function AnimPlayer.Play(character: Model?, name: string, isLocalCharacter: boolean, opts: any?): Handle?
	if character == nil or character.Parent == nil then
		return nil
	end
	opts = opts or {}
	if AnimPlayer.HasUploaded(name) then
		if not isLocalCharacter then
			return nil
		end
		local animator = getAnimator(character)
		local track = animator and getTrack(animator, name)
		if track == nil then
			return nil
		end
		track:Play(opts.FadeTime or 0.08, opts.Weight or 1, opts.Speed or 1)
		local handle = {}
		function handle.Stop(_, fadeTime: number?)
			track:Stop(fadeTime or 0.15)
		end
		function handle.AdjustSpeed(_, speed: number)
			track:AdjustSpeed(speed)
		end
		return handle :: any
	end
	if not Config.UseKeyframeFallback then
		return nil
	end
	return playFallback(character, name, opts)
end

function AnimPlayer.StopAll(character: Model, fadeTime: number?)
	local st = active[character]
	if st then
		for _, tr in ipairs(st.tracks) do
			if tr.stopAt == nil or tr.stopAt > os.clock() then
				tr.stopAt = os.clock()
				tr.fadeOut = fadeTime or 0.15
			end
		end
	end
	local animator = getAnimator(character)
	local cache = animator and animatorTracks[animator]
	if cache then
		for _, track in pairs(cache) do
			if track.IsPlaying then
				track:Stop(fadeTime or 0.15)
			end
		end
	end
end

function AnimPlayer.Length(name: string): number
	local data = compile(name)
	return data and data.length or 0
end

-- Önceden derle (ilk kullanımda takılma olmasın)
task.defer(function()
	for name in pairs(Config.AnimationIds) do
		compile(name)
	end
end)

return AnimPlayer
