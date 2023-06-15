from __future__ import print_function
from os import access
from numpy.core.fromnumeric import var
from ortools.linear_solver import pywraplp
# from ortools.linear_solver.pywraplp import Variable
import sys
import AST
import Constraints
from pprint import pprint

# * calculate pad around the image and store them as tuple (top,bottom,left,right)
def calculatePad(stencils:dict):
	pad={}
	for producer in stencils.keys():
		pad[producer]={}
		for consumer in stencils[producer].keys():
			sw=stencils[producer][consumer][0]
			if sw%2==0:
				left=int((sw-2)/2)
				right=int(sw/2)
			else:
				left=right=int((sw-1)/2)
			sh=stencils[producer][consumer][1]
			if sh%2==0:
				top=int(sh/2)
				bottom=int((sh-2)/2)
			else:
				top=bottom=int((sh-1)/2)
			pad[producer][consumer]=(top,bottom,left,right)
	return pad            
			

def revDependency(dependency:dict):
	revDep={}
	for producer in dependency.keys():
		for consumer in dependency[producer].keys():
			if consumer not in revDep.keys():
				revDep[consumer]=[]
			revDep[consumer].append(producer)
	return revDep


def calcCompCycles(revDep:dict,stencils:dict,pad:dict,variable:list,node:str,scs,newSCS:dict,virtStage:dict):
	# print(f"current node {node}")
	if(node in AST.inputStages):
		newSCS[node]=0
		return 0
	maxProducer=''
	maxCycle=-1
	# print(f"node is {node}")
	# pprint(revDep)
	for producer in revDep[node]:
		# print(f"hello")
		# print(f"Calculating comp cycles for {producer} {node}")
		if producer not in pad.keys() and producer[:-2] in virtStage.keys():
			temp=calcCompCycles(revDep,stencils,pad,variable,producer,scs,newSCS,virtStage)+stencils[virtStage[producer[:-2]][0]][node][0]-pad[virtStage[producer[:-2]][0]][node][2]
		elif producer in pad.keys():
			temp=calcCompCycles(revDep,stencils,pad,variable,producer,scs,newSCS,virtStage)+stencils[producer][node][0]-pad[producer][node][2]
		else:
			print("The AST isn't correct. Exitnig...")
			exit()
		# print(temp)
		if temp>maxCycle:
			maxCycle=temp
			maxProducer=producer
		# print(f"current producer is {producer}")
	# print(f"{maxProducer}")
	newSCS[node]=maxCycle
	return newSCS[node]


def SolverMain(file,width:int,sram:int,combine=False):
	# Create the mip solver with the CBC backend.
	solver = pywraplp.Solver.CreateSolver('CBC')

	#define infinity
	infinity = solver.infinity()

	# generate the matrices for optimisation problemleftPadMask
	A,B,C,variable,dependency,stencils,pad,readRegs,accessLevels,virtStage=Constraints.generatorMain(file,width=width,sram=sram,combine=combine)
	# pad=calculatePad(stencils)
	
	print("============ependency===========")
	pprint(dependency)
	print("============Stencil==========")
	pprint(stencils)
	print("============Variables=============")
	print(variable)
	print("============A,B,C============")
	print(A,B,C)
	print("============readRegs=============")
	print(readRegs)
	print("============pad=============")
	pprint(pad)
	print("============accessLevels============")
	print(accessLevels)
	print("============virtStage============")
	pprint(virtStage)

	# initialise the solver variables
	scs = {}
	for j in range(len(variable)):
		# maxTopPad=0
		# if j<len(variable)-1:
		# 	for con in pad[variable[j]].keys():
		# 		if(pad[variable[j]][con][0]>maxTopPad):
		# 			maxTopPad=pad[variable[j]][con][0]
		scs[j] = solver.IntVar(0, infinity, variable[j])
	print('Number of variables =', solver.NumVariables())

	# initialise the solver constraints
	for i in range(len(B)):
		constraint = solver.RowConstraint(-infinity, float(B[i]), '')
		for j in range(len(variable)):
			constraint.SetCoefficient(scs[j], float(A[i][j]))
	

	# Constraint the virtual stages to atart together.
	for stage in virtStage.keys():
		v1 = virtStage[stage][0]
		v2 = virtStage[stage][1]
		constraint = solver.RowConstraint(0,0,'')
		for j in range(len(variable)):
			if v1==variable[j]:
				constraint.SetCoefficient(scs[j], -1.0)
			elif v2==variable[j]:
				constraint.SetCoefficient(scs[j], 1.0)
			else:
				constraint.SetCoefficient(scs[j], 0.0)
	print('Number of constraints =', solver.NumConstraints())
	
	# set the objective function
	objective = solver.Objective()
	for j in range(len(variable)):
		objective.SetCoefficient(scs[j], float(C[j]))
	objective.SetMinimization()

	# solve
	status = solver.Solve()
	if status == pywraplp.Solver.OPTIMAL:
		print('Objective value =', solver.Objective().Value())
		for j in range(len(variable)):
			print(scs[j].name(), ' = ', scs[j].solution_value())
		print()
		print('Problem solved in %f milliseconds' % solver.wall_time())
		print('Problem solved in %d iterations' % solver.iterations())
		print('Problem solved in %d branch-and-bound nodes' % solver.nodes())
	else:
		print('The problem does not have an optimal solution.')
		exit()
	
	# Calculate the actual start cycles.
	revDep=revDependency(dependency)
	# print("==============revdep===============")
	# pprint(revDep)
	newSCS={}
	if AST.outputStage not in virtStage.keys():
		calcCompCycles(revDep,stencils,pad,variable,AST.outputStage,scs,newSCS,virtStage)
	else:
		calcCompCycles(revDep,stencils,pad,variable,virtStage[AST.outputStage][0],scs,newSCS,virtStage)
		newSCS[virtStage[AST.outputStage][1]] = newSCS[virtStage[AST.outputStage][0]]
	for i in range(len(variable)):
		node=scs[i].name()
		newSCS[node]+=int(scs[i].solution_value())
	print(newSCS)
	# print(accessLevels)
	return dependency,stencils,scs,readRegs,pad,newSCS,accessLevels,virtStage


if __name__ == "__main__":
	Input=sys.argv[1]
	file=open(Input,'r')
	width=1920
	sram=8
	combine = False
	SolverMain(file,width,sram,combine)