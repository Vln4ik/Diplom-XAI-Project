on run
	set scriptPath to "/Users/vinchik/Desktop/Diplom/infra/start_backend_stack.sh"
	tell application "Terminal"
		activate
		do script "bash " & quoted form of scriptPath
	end tell
end run
