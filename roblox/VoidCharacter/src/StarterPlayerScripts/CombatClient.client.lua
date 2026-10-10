-- CombatClient (LocalScript) -> StarterPlayer > StarterPlayerScripts
-- Sol tık = düz vuruş (basılı tutarsan art arda vurur).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")

print("[Combat] CombatClient başladı")
local remote = ReplicatedStorage:WaitForChild("CombatM1", 10)
if not remote then
	error("[Combat] CombatM1 yok -> CombatServer çalışmıyor (ServerScriptService'te Script olmalı)")
end

local player = Players.LocalPlayer
local holding = false
local holdId = 0

local function attack()
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if hum and hum.Health > 0 then
		remote:FireServer()
	end
end

UserInputService.InputBegan:Connect(function(input, processed)
	if processed then
		return
	end
	if input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then
		holding = true
		holdId += 1
		local myId = holdId
		attack()
		task.spawn(function()
			while holding and holdId == myId do
				task.wait(0.34)
				if holding and holdId == myId then
					attack()
				end
			end
		end)
	end
end)

UserInputService.InputEnded:Connect(function(input)
	if input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then
		holding = false
	end
end)

print("[Combat] CombatClient hazır")
