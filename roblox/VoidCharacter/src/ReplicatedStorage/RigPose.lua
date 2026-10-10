-- RigPose (ModuleScript) -> ReplicatedStorage
-- Animasyon dosyası olmadan eklemleri (omuz, dirsek, bilek, boyun, bel) döndürür.
-- Hem eski Motor6D hem de yeni AnimationConstraint eklemleriyle çalışır.
-- Sunucuda çağrılırsa herkes görür.

local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local RigPose = {}

local original = setmetatable({}, { __mode = "k" })
local active = setmetatable({}, { __mode = "k" })

local JOINT_NAMES = {
	"RightShoulder", "LeftShoulder", "RightElbow", "LeftElbow",
	"RightWrist", "LeftWrist", "Neck", "Waist",
	"RightHip", "LeftHip", "RightKnee", "LeftKnee",
}

local function findJoint(char, name)
	for _, d in ipairs(char:GetDescendants()) do
		if d.Name == name and (d:IsA("Motor6D") or d:IsA("AnimationConstraint")) then
			return d
		end
	end
	return nil
end

-- Motor6D -> C0, AnimationConstraint -> Attachment0.CFrame
local function handle(joint)
	if not joint then
		return nil
	end
	if joint:IsA("Motor6D") then
		local ok = pcall(function()
			joint.C0 = joint.C0
		end)
		if ok then
			return joint, "C0"
		end
	end
	local ok, att = pcall(function()
		return joint.Attachment0
	end)
	if ok and att then
		return att, "CFrame"
	end
	return nil
end

local function lerpTo(obj, prop, target, time, style)
	local start = obj[prop]
	local token = {}
	active[obj] = token
	if time <= 0 then
		pcall(function()
			obj[prop] = target
		end)
		return
	end
	local t0 = os.clock()
	local conn
	conn = RunService.Heartbeat:Connect(function()
		if active[obj] ~= token or not obj.Parent then
			conn:Disconnect()
			return
		end
		local a = math.clamp((os.clock() - t0) / time, 0, 1)
		local e = TweenService:GetValue(a, style, Enum.EasingDirection.Out)
		pcall(function()
			obj[prop] = start:Lerp(target, e)
		end)
		if a >= 1 then
			conn:Disconnect()
		end
	end)
end

-- poses = { RightShoulder = CFrame.Angles(...), ... }  (orijinal duruşa göre dönüş)
function RigPose.set(char, poses, time, style)
	for name, rot in pairs(poses) do
		local obj, prop = handle(findJoint(char, name))
		if obj then
			original[obj] = original[obj] or obj[prop]
			lerpTo(obj, prop, original[obj] * rot, time or 0.25, style or Enum.EasingStyle.Quad)
		end
	end
end

function RigPose.reset(char, time)
	local poses = {}
	for _, name in ipairs(JOINT_NAMES) do
		poses[name] = CFrame.identity
	end
	RigPose.set(char, poses, time or 0.3)
end

return RigPose
