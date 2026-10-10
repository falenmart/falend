-- CharacterSelectServer (Script) -> ServerScriptService
-- Oyuncu menüden karakter seçince: seçimi kaydeder, oyuncuyu öldürür ve otomatik yeniden doğurur.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

print("[Select] CharacterSelectServer başladı")
local CharacterList = require(ReplicatedStorage:WaitForChild("CharacterList"))

local valid = {}
for _, c in ipairs(CharacterList) do
	valid[c.Id] = true
end

local remote = Instance.new("RemoteEvent")
remote.Name = "SelectCharacter"
remote.Parent = ReplicatedStorage

local lastSwitch = {}
local RESPAWN_DELAY = 1.5

remote.OnServerEvent:Connect(function(player, id)
	if typeof(id) ~= "string" or not valid[id] then
		return
	end
	if player:GetAttribute("SelectedCharacter") == id then
		return
	end
	local now = os.clock()
	if lastSwitch[player] and now - lastSwitch[player] < 3 then
		return
	end
	lastSwitch[player] = now

	player:SetAttribute("SelectedCharacter", id)

	-- Öl ve yeni güçle yeniden doğ
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if hum and hum.Health > 0 then
		hum.Health = 0
	end
	task.delay(RESPAWN_DELAY, function()
		if player.Parent then
			player:LoadCharacter()
		end
	end)
end)

Players.PlayerAdded:Connect(function(player)
	if player:GetAttribute("SelectedCharacter") == nil then
		player:SetAttribute("SelectedCharacter", "None")
	end
end)
for _, p in ipairs(Players:GetPlayers()) do
	if p:GetAttribute("SelectedCharacter") == nil then
		p:SetAttribute("SelectedCharacter", "None")
	end
end

Players.PlayerRemoving:Connect(function(player)
	lastSwitch[player] = nil
end)

print("[Select] CharacterSelectServer hazır")
