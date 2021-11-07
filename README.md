# Hydra Render Farm
A simple MySQL based render farm software. No central queue server, just a list of jobs and tasks on a MySQL table that
the various systems interact with. 

## Features
* Prioritization 
* Provisioning via node "Capabilities" and job "Requirements"
* Blacklisting nodes which fail to complete a task
* Farm Management via FarmView
  * Controlling Job, Task, and Node status
  * Editing Nodes
  * Killing Tasks with TCP Connections to the Render Host
  * Prioritizing Jobs
  * Archiving Jobs
  * Basic filtering by current user
* Submission via Submitter
  * Render Jobs, MayaPy Jobs, Batch File Jobs
  * Dynamic GUI
  * Setting Frame Ranges, Render Layers, Output Paths, Command Line Args, etc. 

## Not Working
* Render Node GUI `render_node_ui.py`

## System Diagram
![Hydra Diagram](docs/hydra_diagram.png?raw=true "Diagram")

## FarmView GUI
![FarmView GUI Screenshot](docs/farmview.png?raw=true "FarmView GUI")

## Submitter GUI
![Submitter GUI Screenshot](docs/submitter.png?raw=true "Submitter GUI")