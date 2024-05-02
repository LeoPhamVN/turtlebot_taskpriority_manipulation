from .common import *
import math
import numpy as np

class ManipulatorParams:
    def __init__(self) -> None:
        self.dof = 4       
        self.bx = 0.0132        # [met]
        self.bz = 0.108         # [met]
        self.d1 = 0.142         # [met]
        self.d2 = 0.1588        # [met]
        self.mz = 0.0722        # [met]
        self.mx = 0.0565        # [met]
class MobileManipulator:
    '''
        Constructor.

        Arguments:
        d (Numpy array): list of displacements along Z-axis
        theta (Numpy array): list of rotations around Z-axis
        a (Numpy array): list of displacements along X-axis
        alpha (Numpy array): list of rotations around X-axis
        revolute (list of Bool): list of flags specifying if the corresponding joint is a revolute joint
    '''
    def __init__(self):
        self.revolute = [True, True, True, True]

        self.manipulatorParams = ManipulatorParams()

        # List of joint types extended with base joints
        self.revoluteExt = [True, False] + self.revolute

        self.dof = 4 #len(self.revoluteExt)  # Number of DOF of the system

        # Vector of joint positions (manipulator)
        self.q = np.zeros((len(self.revolute), 1))
        self.q_hist = []

        # Vector of base pose (position & orientation)
        self.eta = np.zeros((4, 1))

        # Initialise robot state
        # self.update(np.zeros((self.dof, 1)), 0.0)

    '''
        Method that updates the state of the robot.

        Arguments:
        dQ (Numpy array): a column vector of quasi velocities
        dt (double): sampling time
    '''
    
    def rotate_then_move(self,dQ,dt):
        angular_vel = dQ[0, 0]
        forward_vel = dQ[1, 0]
        yaw = self.eta[2, 0]

        # Apply rotation first
        self.eta[2, 0] += angular_vel * dt
        yaw = self.eta[2, 0]

        # Then apply forward movement
        self.eta += dt * np.array([forward_vel * np.cos(yaw), forward_vel * np.sin(yaw), 0]).reshape(3, 1)
    
    def move_then_rotate(self,dQ,dt):
        # Update mobile base pose
        forward_vel = dQ[1, 0]
        angular_vel = dQ[0, 0]
        yaw = self.eta[2, 0]

        self.eta += dt * np.array([forward_vel * np.cos(yaw), forward_vel * np.sin(yaw), angular_vel]).reshape(3, 1)
    
    def move_and_rotate_simultaneously(self,dQ,dt):
        forward_vel = dQ[1, 0]
        angular_vel = dQ[0, 0]
        R=forward_vel/angular_vel
        ICC=np.array([[self.eta[0]-(R*np.sin(self.eta[2,0])),self.eta[1]+(R*np.cos(self.eta[2,0]))]]).reshape(2,1)
        a=np.array([[np.cos(angular_vel*dt),-np.sin(angular_vel*dt), 0 ],
                    [np.sin(angular_vel*dt),np.cos(angular_vel*dt), 0 ],
                    [0,0,1]]).reshape(3,3)
        b=np.array([[self.eta[0,0]-ICC[0,0]],
                    [self.eta[1,0]-ICC[1,0]],
                    [self.eta[2,0]]]).reshape(3,1)
        c=np.block([[ICC],[angular_vel*dt]]).reshape(3,1)
        self.eta= (a @ b) + c
        
    
    def update(self, dQ, dt,mobile_base_kinematics_integration="MTR"):
        # Update manipulator
        self.q += dQ[2:, 0].reshape(-1, 1) * dt
        self.q_hist.append(self.q)
        for i in range(len(self.revolute)):
            if self.revolute[i]:
                self.theta[i] = self.q[i]
            else:
                self.d[i] = self.q[i]

        # Update mobile base pose
        if mobile_base_kinematics_integration=="MTR":
            self.move_then_rotate(dQ,dt)
        elif mobile_base_kinematics_integration=="RTM":
            self.rotate_then_move(dQ,dt)
        elif mobile_base_kinematics_integration=="MRS":
            self.move_and_rotate_simultaneously(dQ,dt)

        # Base kinematics
        x, y, yaw = self.eta.flatten()
        Tb= getTransformation("lin",'x',x)@getTransformation("lin","y",y)@ getTransformation("ang","z",yaw)
        
        # Following code can be used to get the series of Transformations
        '''
        Tb = getTotalTransformation(["ang","ang",
                                     "ang","ang",
                                     "ang",
                                     "lin","ang",
                                     "lin","ang","ang",
                                     "lin","lin"],
                                    ["z","x"
                                    "z","x",
                                    "z",
                                    "z","x",
                                    "z","z","x",
                                    "z","x"],
                                    [yaw,-np.pi/2,
                                    np.pi/2,np.pi/2,
                                    0,
                                    0,-np.pi/2,
                                    0,-np.pi/2,np.pi/2,
                                    0,self.r])  # Transformation of the mobile base

        ## Additional rotations performed, to align the axis:
        Rotate Z +90 (using the theta of the first base joint)
        Rotate X +90 (using the alpha of the first base joint)
        # Z now aligns with the forward velocity of the base
        Rotate X -90 (using the alpha of the second base joint)
        # Z is now back to vertical position
        Rotate Z -90 (using the theta of the first manipulator joint)
        '''

        # Modify the theta of the base joint, to account for an additional Z rotation
        self.theta[0] -= deg90

        # Combined system kinematics (DH parameters extended with base DOF)
        dExt = np.concatenate([np.array([0, self.r]), self.d])
        thetaExt = np.concatenate([np.array([deg90, 0]), self.theta])
        aExt = np.concatenate([np.array([0, 0]), self.a])
        alphaExt = np.concatenate([np.array([deg90, -deg90]), self.alpha])

        self.T = kinematics(dExt, thetaExt, aExt, alphaExt, Tb)


    ''' 
        Method that returns the characteristic points of the robot.
    '''
    # def drawing(self):
    #     return robotPoints2D(self.T)

    '''
        Method that returns the end-effector Jacobian.
    '''
    # def getEEJacobian(self):
    #     return jacobian(self.T, self.revoluteExt)

    '''
        Method that returns the end-effector transformation.
    '''
    def getEETransform(self):
        return self.T[-1]

    '''
        Method that returns the position of a selected joint.

        Argument:
        joint (integer): index of the joint

        Returns:
        (double): position of the joint
    '''
    def getJointPos(self, joint):
        return self.q[joint-1]


    def getBasePose(self):
        return self.eta

    '''
        Method that returns number of DOF of the manipulator.
    '''
    def getDOF(self):
        return self.dof

    ###
    def getLinkJacobian(self, link):
        return jacobianLink(self.T, self.revoluteExt, link)

    def getLinkTransform(self, Link):
        if Link > self.getDOF():
            return self.T[-1]
        else:
            return self.T[Link]
    
    def track_q(self):
        # self.q_hist.append(((np.rad2deg(self.q))% 360 + 360) % 360)
        # self.q_hist.append((np.rad2deg(self.theta)))
        self.q_hist.append(self.q)
    
    def reset(self):
        # Reset the robot's state to the initial conditions
        self.q = np.zeros((len(self.revolute), 1))
        self.eta = np.zeros((3, 1))
        self.update(np.zeros((self.dof, 1)), 0.0)

    '''
        Method that returns the end-effector Jacobian.
    '''
    def getEEJacobian(self): 
        J = np.zeros((6, self.manipulatorParams.dof))
        q1, q2, q3, q4  = self.q
    
        l1p     = -self.manipulatorParams.d1 * math.sin(q2)               #projection of d1 on x-axis 
        l2p     =  self.manipulatorParams.d2 * math.cos(q3)               #projection of d2 on x-axis
        l       =  self.manipulatorParams.bx + l1p + l2p + self.manipulatorParams.mx    #total length from base to ee top projection 

        # dx_db1  = 
        dx_dq1  = -l * math.sin(q1) * math.cos(self.eta[3]) - l * math.cos(q1) * math.sin(self.eta[3]) 
        dy_dq1  = -l * math.sin(q1) * math.sin(self.eta[3]) + l * math.cos(q1) * math.cos(self.eta[3])
        
        
        dx_dq2  = -self.manipulatorParams.d1 * math.cos(q2) * (math.cos(q1) * math.cos(self.eta[3]) - math.sin(q1) * math.sin(self.eta[3])) 
        dy_dq2  = -self.manipulatorParams.d1 * math.cos(q2) * (math.cos(q1) * math.sin(self.eta[3]) + math.sin(q1) * math.cos(self.eta[3])) 
        dz_dq2  =  self.manipulatorParams.d1 * math.sin(q2)


        dx_dq3  = -self.manipulatorParams.d2 * math.sin(q3) * (math.cos(q1) * math.cos(self.eta[3]) - math.sin(q1) * math.sin(self.eta[3])) 
        dy_dq3  = -self.manipulatorParams.d2 * math.sin(q3) * (math.cos(q1) * math.cos(self.eta[3]) - math.sin(q1) * math.sin(self.eta[3])) 
        dz_dq3  = -self.manipulatorParams.d2 * math.cos(q3)

        # J[:, 0] = np.array([])
        J[:, 0] = np.array([dx_dq1, dy_dq1,      0, 0, 0, 1])   # derivertive by q1
        J[:, 1] = np.array([dx_dq2, dy_dq2, dz_dq2, 0, 0, 0])   # derivertive by q2
        J[:, 2] = np.array([dx_dq3, dy_dq3, dz_dq3, 0, 0, 0])   # derivertive by q3
        J[:, 3] = np.array([0, 0, 0, 0, 0, 1])                  # derivertive by q4

        return J
        
    def getEEposition(self):
        q1, q2, q3, q4 = self.q

        l1p     = -self.manipulatorParams.d1 * math.sin(q2)               #projection of d1 on x-axis 
        l2p     =  self.manipulatorParams.d2 * math.cos(q3)               #projection of d2 on x-axis
        l       =  self.manipulatorParams.bx + l1p + l2p + self.manipulatorParams.mx    #total length from base to ee top projection 
 
        #forward kinematics to get ee position     
        x = l * math.cos(q1) + self.eta[0]
        y = l * math.sin(q1) + self.eta[1]
        z =-(self.manipulatorParams.bz + self.manipulatorParams.d1 * math.cos(-q2) + self.manipulatorParams.d2 * math.sin(q3) - self.manipulatorParams.mz) + self.eta[2]
        yaw = q1 + q4 + self.eta[3] 

        return np.array([x, y, z]).reshape(3,1)
    
    def update(self, jointState):
        self.q      = jointState.SwiftProJoint.position
        self.eta    = np.zeros((4, 1))

           
        