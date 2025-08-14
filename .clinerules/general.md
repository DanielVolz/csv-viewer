# General Rules for CSV Viewer Development

- ask questions if something is unclear
- never fix flake or general linter errors
- we are using a dockerized dev env to develop. ou dont need to restart the app. the changes are instant.
- when using docker compose up wait 30 seconds before you try to input another command into terminal because when docker is not finished upping the stack it will cancel the task when you input another command
- dont open the browser in cline if the check could be done with curl on an endpoint