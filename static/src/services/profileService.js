angular.module('profileService', [
  ])



  .factory("ProfileService", function(){
    return {
      foo: function(){
        return "i am in the profile service"
      },

      createProfile: function(name, pmids) {
        console.log("i am making a profile:", name, pmids)
      }
    }


  })